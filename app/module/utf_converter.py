
import os

# 参考
#  https://gist.github.com/benjaminestes/5817f81288ccd89f603862cd9a997735

def utf16_to_utf8(path_list:list):

    for path in path_list:
        with open(path, "rb") as source:
            with open("{0}-utf8.csv".format(path), "wb") as dest:
                dest.write(source.read().decode("utf-16").encode("utf-8"))

        os.remove(path)
