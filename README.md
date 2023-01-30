# cbc-nlp : The "consileon NLP framework"

## Installation
- Install via: `py -m pip install --index-url https://test.pypi.org/simple/ --no-deps cbc-nlp` or using the [requirements.txt](requirements.txt)
- Install the relevant `spaCy` model through `$ python -m spacy download [model]`. For further details, see the [spaCy Website](https://spacy.io/usage/models#download)

## Why Consileon NLP Framework?
NLP models are developed based on text sources which contain (long) sequences of texts. A major part of the development is the pre-processing of input data. Most effort and time is spent on transforming text into other objects (lists of tokens) in order to be handled by NLP algorithms. This is where Consileon’s NLP Framework comes into play. 

Consileon NLP Framework contains packages that simplify the development of NLP models through modularization and encapsulation of frequent pre-processing tasks. In that way, you avoid repeating yourself or ending up with a bulk of unstructured sample code that you might not understand or be able to explain later on. Focus on your concept and leave the implementation on us.  

## Features: 
Consileon NLP Framework offers all preprocessing tasks you need to develop your own NLP Model: 

- **Split** texts into smaller chunks (sentences, paragraphs) 
- Split chunks of text into **tokens** (e.g. single words) 
- Bring tokens into a canonical form (**lower-casing**) 
- **Filter** out unwanted tokens and **remove stop words**. 
- "**Lemmatization**":  map words to their base/dictionary form (imported also for many non-english languages) 
- **Perform** (other kinds of) **mappings** to tokens 
- **Remove "garbage"**, i.e. artifacts which are contained in the source but don’t add meaning to the use case at hand (e.g. remove tables of numbers from texts when spoken language is required) 
- **Append** tags to tokens (e.g. specify the source or some semantic information) 
- **Choose subsets** of the input sequence for development (or other) reasons 
- **Merge** several data sources. 

and **many more**. 

All these transformation steps can be pipelined in few coding lines and fed into NLP-algorithms to generate your NLP model.   



## Getting started: 
The following tutorial will walk you through developing your own NLP-Model using Consileon’s NLP Framework:  
See [getting_startet.ipynb](examples/notebooks/getting_started.ipynb)

---

## Developer Notes

### Set-up
Create a virtual environment
```
py -3 -m venv .venv
.venv\scripts\activate
```
Now install the package i) as an editible install (so code changes come into effect without a re-install) and ii) with the dev option (to have access to dev requirements such as `pytest`)
```
python -m pip install -e .[dev]
```

### Distribution/ Versioning
If necessary, update the version number in the `pyproject.toml`.

Next, update the software and build package in `dist\` folder
```Bash
pip install --upgrade build
python -m build
```

Finally, upload to the distribution archive using `twine`. Note, for experimental changes you can upload to `testPyPI` first, before uploading to `PyPI`.
```Bash
pip install --upgrade twine
python -m twine upload --repository testpypi dist/*
```
When asked, set username to "`__token__`" and your password to the respective token.

If this doesn't work, add token directly into CLI command
```
python -m twine upload --repository testpypi dist/* -u __token__ -p YOUR_RESPECTIVE_TOKEN
```

### requirements.txt file
For development purposes, there also exists a set of `requirements.txt` files, where the `dev-requirements.txt` file again includes additional packages such as `pytest`.

Generally, the `requirements.txt` are maintained and updated via `pip-compile` using the following command
```Bash
pip-compile --no-annotate --output-file=requirements.txt pyproject.toml
```

To update the `dev-requirements.txt`, use
```Bash
pip-compile --no-annotate --extra dev --output-file=dev-requirements.txt pyproject.toml
```









