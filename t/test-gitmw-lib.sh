# Copyright (C) 2012
#     Charles Roussel <charles.roussel@ensimag.imag.fr>
#     Simon Cathebras <simon.cathebras@ensimag.imag.fr>
#     Julien Khayat <julien.khayat@ensimag.imag.fr>
#     Guillaume Sasdy <guillaume.sasdy@ensimag.imag.fr>
#     Simon Perrat <simon.perrat@ensimag.imag.fr>
# License: GPL v2 or later

#
# CONFIGURATION VARIABLES
# You might want to change these ones
#

. ./test.config

WIKI_BASE_URL=http://$SERVER_ADDR:$PORT
WIKI_URL=$WIKI_BASE_URL/$WIKI_DIR_NAME
CURR_DIR=$(pwd)
TEST_OUTPUT_DIRECTORY=$(pwd)

export TEST_OUTPUT_DIRECTORY CURR_DIR

if test "$LIGHTTPD" = "false" ; then
	PORT=80
else
	WIKI_DIR_INST="$CURR_DIR/$WEB_WWW"
fi

die () {
	die_with_status 1 "$@"
}

die_with_status () {
	status=$1
	shift
	echo >&2 "$*"
	exit "$status"
}

# Use this instead of "grep expected-string actual" to see if the
# output from a git command that can be translated either contains an
# expected string, or does not contain an unwanted one.  When running
# under GETTEXT_POISON this pretends that the command produced expected
# results.
test_i18ngrep () {
	if test -n "$GETTEXT_POISON"
	then
		: # pretend success
	elif test "x!" = "x$1"
	then
		shift
		! grep "$@"
	else
		grep "$@"
	fi
}

# ================= Install part =================

error () {
	echo "$@" >&2
	exit 1
}

# config_lighttpd
#
# Create the configuration files and the folders necessary to start lighttpd.
# Overwrite any existing file.
config_lighttpd () {
	mkdir -p $WEB
	mkdir -p $WEB_TMP
	mkdir -p $WEB_WWW
	cat > $WEB/lighttpd.conf <<EOF
	server.document-root = "$CURR_DIR/$WEB_WWW"
	server.port = $PORT
	server.pid-file = "$CURR_DIR/$WEB_TMP/pid"

	server.modules = (
	"mod_rewrite",
	"mod_redirect",
	"mod_access",
	"mod_accesslog",
	"mod_fastcgi"
	)

	index-file.names = ("index.php" , "index.html")

	mimetype.assign		    = (
	".pdf"		=>	"application/pdf",
	".sig"		=>	"application/pgp-signature",
	".spl"		=>	"application/futuresplash",
	".class"	=>	"application/octet-stream",
	".ps"		=>	"application/postscript",
	".torrent"	=>	"application/x-bittorrent",
	".dvi"		=>	"application/x-dvi",
	".gz"		=>	"application/x-gzip",
	".pac"		=>	"application/x-ns-proxy-autoconfig",
	".swf"		=>	"application/x-shockwave-flash",
	".tar.gz"	=>	"application/x-tgz",
	".tgz"		=>	"application/x-tgz",
	".tar"		=>	"application/x-tar",
	".zip"		=>	"application/zip",
	".mp3"		=>	"audio/mpeg",
	".m3u"		=>	"audio/x-mpegurl",
	".wma"		=>	"audio/x-ms-wma",
	".wax"		=>	"audio/x-ms-wax",
	".ogg"		=>	"application/ogg",
	".wav"		=>	"audio/x-wav",
	".gif"		=>	"image/gif",
	".jpg"		=>	"image/jpeg",
	".jpeg"		=>	"image/jpeg",
	".png"		=>	"image/png",
	".xbm"		=>	"image/x-xbitmap",
	".xpm"		=>	"image/x-xpixmap",
	".xwd"		=>	"image/x-xwindowdump",
	".css"		=>	"text/css",
	".html"		=>	"text/html",
	".htm"		=>	"text/html",
	".js"		=>	"text/javascript",
	".asc"		=>	"text/plain",
	".c"		=>	"text/plain",
	".cpp"		=>	"text/plain",
	".log"		=>	"text/plain",
	".conf"		=>	"text/plain",
	".text"		=>	"text/plain",
	".txt"		=>	"text/plain",
	".dtd"		=>	"text/xml",
	".xml"		=>	"text/xml",
	".mpeg"		=>	"video/mpeg",
	".mpg"		=>	"video/mpeg",
	".mov"		=>	"video/quicktime",
	".qt"		=>	"video/quicktime",
	".avi"		=>	"video/x-msvideo",
	".asf"		=>	"video/x-ms-asf",
	".asx"		=>	"video/x-ms-asf",
	".wmv"		=>	"video/x-ms-wmv",
	".bz2"		=>	"application/x-bzip",
	".tbz"		=>	"application/x-bzip-compressed-tar",
	".tar.bz2"	=>	"application/x-bzip-compressed-tar",
	""		=>	"text/plain"
	)

	fastcgi.server = ( ".php" =>
	("localhost" =>
	( "socket" => "$CURR_DIR/$WEB_TMP/php.socket",
	"bin-path" => "$PHP_DIR/php-cgi -c $CURR_DIR/$WEB/php.ini"

	)
	)
	)
EOF

	cat > $WEB/php.ini <<EOF
	session.save_path ='$CURR_DIR/$WEB_TMP'
EOF
}

# start_lighttpd
#
# Start or restart daemon lighttpd. If restart, rewrite configuration files.
start_lighttpd () {
	if test -f "$WEB_TMP/pid"; then
		echo "Instance already running. Restarting..."
		stop_lighttpd
	fi
	config_lighttpd
	"$LIGHTTPD_DIR"/lighttpd -f "$WEB"/lighttpd.conf

	if test $? -ne 0 ; then
		echo "Could not execute http daemon lighttpd"
		exit 1
	fi
}

# stop_lighttpd
#
# Kill daemon lighttpd and removes files and folders associated.
stop_lighttpd () {
	test -f "$WEB_TMP/pid" && kill $(cat "$WEB_TMP/pid")
}

wiki_delete_db () {
	rm -rf \
	   "$FILES_FOLDER_DB"/* || error "Couldn't delete $FILES_FOLDER_DB/"
}

wiki_delete_db_backup () {
	rm -rf \
	   "$FILES_FOLDER_POST_INSTALL_DB"/* || error "Couldn't delete $FILES_FOLDER_POST_INSTALL_DB/"
}

# Install MediaWiki using its install.php script. If the database file
# already exists, it will be deleted.
install_mediawiki () {

	localsettings="$WIKI_DIR_INST/$WIKI_DIR_NAME/LocalSettings.php"
	if test -f "$localsettings"
	then
		error "We already installed the wiki, since $localsettings exists" \
		      "perhaps you wanted to run 'delete' first?"
	fi

	wiki_delete_db
	wiki_delete_db_backup
	mkdir \
		"$FILES_FOLDER_DB/" \
		"$FILES_FOLDER_POST_INSTALL_DB/"

	install_script="$WIKI_DIR_INST/$WIKI_DIR_NAME/maintenance/install.php"
	echo "Installing MediaWiki using $install_script. This may take some time ..."

	php "$WIKI_DIR_INST/$WIKI_DIR_NAME/maintenance/install.php" \
	    --server $WIKI_BASE_URL \
	    --scriptpath /wiki \
	    --lang en \
	    --dbtype sqlite \
	    --dbpath $PWD/$FILES_FOLDER_DB/ \
	    --pass "$WIKI_PASSW" \
	    Git-MediaWiki-Test \
	    "$WIKI_ADMIN" ||
		error "Couldn't run $install_script, see errors above. Try to run ./install-wiki.sh delete first."
	cat <<-'EOF' >>$localsettings
# Custom settings added by test-gitmw-lib.sh
#
# Uploading text files is needed by the media tests
$wgEnableUploads = true;
$wgFileExtensions[] = 'txt';
EOF

	# Copy the initially generated database file into our backup
	# folder
	cp -R "$FILES_FOLDER_DB/"* "$FILES_FOLDER_POST_INSTALL_DB/" ||
		error "Unable to copy $FILES_FOLDER_DB/* to $FILES_FOLDER_POST_INSTALL_DB/*"
}

# Install a wiki in your web server directory.
wiki_install () {
	if test $LIGHTTPD = "true" ; then
		start_lighttpd
	fi

	# In this part, we change directory to $TMP in order to download,
	# unpack and copy the files of MediaWiki
	(
	mkdir -p "$WIKI_DIR_INST/$WIKI_DIR_NAME"
	if ! test -d "$WIKI_DIR_INST/$WIKI_DIR_NAME"
	then
		error "Folder $WIKI_DIR_INST/$WIKI_DIR_NAME doesn't exist.
		Please create it and launch the script again."
	fi

	# Fetch MediaWiki's archive if not already present in the
	# download directory
	mkdir -p "$FILES_FOLDER_DOWNLOAD"
	MW_FILENAME="mediawiki-$MW_VERSION_MAJOR.$MW_VERSION_MINOR.tar.gz"
	cd "$FILES_FOLDER_DOWNLOAD"
	if ! test -f $MW_FILENAME
	then
		echo "Downloading $MW_VERSION_MAJOR.$MW_VERSION_MINOR sources ..."
		wget "http://download.wikimedia.org/mediawiki/$MW_VERSION_MAJOR/$MW_FILENAME" ||
			error "Unable to download "\
			"http://download.wikimedia.org/mediawiki/$MW_VERSION_MAJOR/"\
			"$MW_FILENAME. "\
			"Please fix your connection and launch the script again."
		echo "$MW_FILENAME downloaded in $(pwd)/;" \
		     "you can delete it later if you want."
	else
		echo "Reusing existing $MW_FILENAME downloaded in $(pwd)/"
	fi
	archive_abs_path=$(pwd)/$MW_FILENAME
	cd "$WIKI_DIR_INST/$WIKI_DIR_NAME/" ||
		error "can't cd to $WIKI_DIR_INST/$WIKI_DIR_NAME/"
	tar xzf "$archive_abs_path" --strip-components=1 ||
		error "Unable to extract WikiMedia's files from $archive_abs_path to "\
			"$WIKI_DIR_INST/$WIKI_DIR_NAME"
	) || exit 1
	echo Extracted in "$WIKI_DIR_INST/$WIKI_DIR_NAME"

	install_mediawiki

	echo "Your wiki has been installed. You can check it at
		$WIKI_URL"
}

# Reset the database of the wiki and the password of the admin
#
# Warning: This function must be called only in a subdirectory of t/ directory
wiki_reset () {
	# Copy initial database of the wiki
	if ! test -d "../$FILES_FOLDER_DB"
	then
		error "No wiki database at ../$FILES_FOLDER_DB, not installed yet?"
	fi
	if ! test -d "../$FILES_FOLDER_POST_INSTALL_DB"
	then
		error "No wiki backup database at ../$FILES_FOLDER_POST_INSTALL_DB, failed installation?"
	fi
	wiki_delete_db
	cp -R "../$FILES_FOLDER_POST_INSTALL_DB/"* "../$FILES_FOLDER_DB/" ||
		error "Can't copy ../$FILES_FOLDER_POST_INSTALL_DB/* to ../$FILES_FOLDER_DB/*"
	echo "File $FILES_FOLDER_DB/* has been reset"
}

# Delete the wiki created in the web server's directory and all its content
# saved in the database.
wiki_delete () {
	if test $LIGHTTPD = "true"; then
		stop_lighttpd
		rm -fr "$WEB"
	else
		# Delete the wiki's directory.
		rm -rf "$WIKI_DIR_INST/$WIKI_DIR_NAME" ||
			error "Wiki's directory $WIKI_DIR_INST/" \
			"$WIKI_DIR_NAME could not be deleted"
	fi
	wiki_delete_db
	wiki_delete_db_backup
}
