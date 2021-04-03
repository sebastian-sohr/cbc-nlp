import consileon.nlp.content as content

h = content.AwsS3ContentHandler("cbc-rss-test", base_prefix="sample_data")

i = h.iterate_lines("rss_tokens.txt")
n = 1
for line in i:
    print(line)
    if n > 10:
        break
    n = n + 1
