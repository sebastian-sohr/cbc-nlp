import cbc.content as content

h = content.FileSystemContentHandler("../../sample_data")

i = h.iterate_lines("rss_tokens.txt")
n = 1
for line in i:
    print(line)
    if n > 10:
        break
    n = n + 1
