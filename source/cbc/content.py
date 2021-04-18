import logging
from abc import ABC, abstractmethod
from pathlib import Path
from os import listdir
from os.path import isfile
from typing import Optional

import boto3
from s3streaming import s3_open, deserialize
import pathlib
import io
import smart_open

logger = logging.getLogger('cbc.nlp.content')


class IteratorReader(io.RawIOBase):

    def __init__(self, iterator, to_bytes_function=lambda x: x):
        self.iterator = iterator
        self.to_bytes_function = to_bytes_function
        self.leftover = []

    def readinto(self, buffer: bytearray) -> Optional[int]:
        size = len(buffer)
        while len(self.leftover) < size:
            try:
                self.leftover.extend(self.to_bytes_function(next(self.iterator)))
            except StopIteration:
                break

        if len(self.leftover) == 0:
            return None

        output, self.leftover = self.leftover[:size], self.leftover[size:]
        buffer[:len(output)] = output
        return len(output)

    def readable(self) -> bool:
        return True


class ContentHandler(ABC):

    def __init__(
        self,
        chunk_size=16384
    ):
        self.chunk_size = chunk_size
        super().__init__()

    @abstractmethod
    def list(self, prefix: str) -> list:
        pass

    @abstractmethod
    def save_text(self, key: str, text: str, prefix=""):
        pass

    @abstractmethod
    def get_text(self, key: str, prefix="") -> str:
        pass

    @abstractmethod
    def save_bytes(self, key, byts: bytes, prefix=""):
        pass

    @abstractmethod
    def get_bytes(self, key: str, prefix="") -> bytes:
        pass

    @abstractmethod
    def iterate_lines(self, key: str, prefix=""):
        pass

    @classmethod
    def append_prefix(cls, base_prefix: str, prefix: str) -> str:
        sep = ""
        if len(base_prefix) > 0 and len(prefix) > 0 and not base_prefix.endswith("/") and not prefix.startswith("/"):
            sep = "/"
        return base_prefix + sep + prefix

    @abstractmethod
    def write_input_stream(self, instream: io.RawIOBase, key: str, prefix=""):
        pass


class FileSystemContentHandler(ContentHandler, ABC):
    def __init__(
        self,
        base_folder='.',
        encoding='utf-8',
        **kwargs
    ):
        self.base_folder = pathlib.Path(base_folder)
        self.encoding = encoding
        super().__init__(**kwargs)

    def get_path(self, prefix=""):
        return self.base_folder / prefix

    def get_full_path(self, key, prefix=""):
        assert(key is not None and len(key) > 0)
        return self.get_path(prefix) / key

    def list(self, prefix=""):
        path = self.get_path(prefix=prefix)
        path.mkdir(parents=True, exist_ok=True)
        return [f for f in listdir(path) if isfile(path / f)]

    def save_text(self, key, text, prefix=""):
        path = self.get_path(prefix=prefix)
        path.mkdir(parents=True, exist_ok=True)
        full_path = path / key
        with full_path.open("w", encoding=self.encoding) as f:
            f.write(text)

    def get_text(self, key, prefix=""):
        text = self.get_full_path(key, prefix=prefix).read_text(encoding=self.encoding)
        return text

    def save_bytes(self, key, byts: bytes, prefix=""):
        path = self.get_path(prefix=prefix)
        path.mkdir(parents=True, exist_ok=True)
        full_path = path / key
        with full_path.open("wb") as f:
            f.write(byts)

    def get_bytes(self, key, prefix=""):
        bytes_ = self.get_full_path(key, prefix=prefix).read_bytes()
        return bytes_

    def iterate_lines(self, key, prefix=""):
        with open(self.get_full_path(key, prefix=prefix), 'r') as file:
            for line in file:
                yield line
            file.close()

    def write_input_stream(self, instream: io.RawIOBase, key: str, prefix=""):
        with open(self.get_full_path(key, prefix=prefix), 'wb') as fout:
            while True:
                r = instream.read(self.chunk_size)
                if r is None:
                    break
                fout.write(r)


class AwsS3ContentHandler(ContentHandler, ABC):
    def __init__(
        self,
        bucket=None,
        base_prefix='',
        encoding='utf-8',
        **kwargs
    ):
        assert(bucket is not None)
        self.bucket = bucket
        self.base_prefix = base_prefix
        self.encoding = encoding
        self.client = boto3.client('s3')
        super().__init__(**kwargs)

    def get_full_key(self, key, prefix=""):
        return self.append_prefix(self.append_prefix(self.base_prefix, prefix), key)

    def list(self, prefix=""):
        result = []
        full_prefix = self.append_prefix(self.base_prefix, prefix)
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=full_prefix)
        replace = ""
        if len(full_prefix) > 0 and not full_prefix.endswith("/"):
            replace = full_prefix + "/"
        while True and response.get("Contents"):
            contents = response["Contents"]
            result.extend([i["Key"].replace(replace, "") for i in contents])
            if not response["IsTruncated"]:
                break
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                ContinuationToken=response['NextContinuationToken'],
                Prefix=full_prefix
            )
        return result

    def save_text(self, key, text, prefix=""):
        self.client.put_object(
            Bucket=self.bucket,
            Key=self.get_full_key(key, prefix=prefix),
            ContentEncoding=self.encoding,
            Body=text.encode(self.encoding)
        )

    def get_text(self, key, prefix=""):
        response = self.client.get_object(Bucket=self.bucket, Key=self.get_full_key(key, prefix=prefix))
        text = response['Body'].read().decode(response['ContentEncoding'])
        return text

    def save_bytes(self, key, bytes_: bytes, prefix=""):
        self.client.put_object(
            Bucket=self.bucket,
            Key=self.get_full_key(key, prefix=prefix),
            Body=bytes_
        )

    def get_bytes(self, key, prefix=""):
        response = self.client.get_object(Bucket=self.bucket, Key=self.get_full_key(key, prefix=prefix))
        bytes_ = response['Body'].read()
        return bytes_

    def iterate_lines(self, key, prefix=""):
        with s3_open(
                "s3://" + self.bucket + "/" + self.get_full_key(key, prefix=prefix),
                boto_session=boto3.session.Session(),
                deserializer=deserialize.string
        ) as file:
            for line in file:
                yield line
            file.close()

    def write_input_stream(self, instream: io.RawIOBase, key: str, prefix=""):
        full_prefix = self.append_prefix(self.base_prefix, prefix)
        full_key = self.append_prefix(full_prefix, key)

        with smart_open.smart_open(self.bucket + "/" + full_key, 'wb') as fout:
            while True:
                r = instream.read(self.chunk_size)
                if r is None:
                    break
                fout.write(r)
