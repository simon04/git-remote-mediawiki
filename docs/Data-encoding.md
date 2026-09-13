# UTF-8 Encoding

Data encoding is a little tricky here. The mediawiki should be encoded in utf8. However, our script is caught in between git and mediawiki. That's a lot to consider.

Typically, every character is authorized in the URL of a mediawiki page (and consequently its title). When the file is to be imported locally, a correct file name has to be found. UTF-8 encoding is the best to allow this. It is very important to make sure that mediawiki files and local files keep the same encoding for both its title and its content.

## Mediawiki -> Git

Since utf8 is the norm, the real character that raises a problem is '/'. It needs to be replaced somehow to avoid unwanted directories to be created. In the script, it is replaced by the string in the `SLASH_REPLACEMENT` constant.

## Git -> Mediawiki

The data that need to be send to mediawiki are stored in git blobs. To get that data, the command `git cat-file blob <sha1>` is used. Consequently, further encoding is needed here

	subprocess.run(['git', *args], stdout=subprocess.PIPE).stdout.decode('utf-8')

This helps encoding in-file data. Media files are read as raw bytes instead, so
that their content is not mangled.

To get titles, a `git diff` command is used. If it is used without the '-z' parameter, non-iso characters are weirly encoded with \\###\\### type of characters. Furthermore, everything we send to the mediawiki API is UTF-8 encoded.

## Further implementation regarding encoding

* Different file systems have different ways to handle non-iso characters in file names. That implies that every file should not have this type of characters in its name. To get rid of this, a smart use of URL-escaping could be used. We ran into some problems since, because of the utf8 general encoding of the file, unquoting is not the inverse of quoting.
