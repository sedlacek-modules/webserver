# Simple python3 webserver with upload
_Licensed under BSD3 license_ 

_Copyright (c) 2021, Ing. Jaromir Sedlacek_
_All rights reserved._

## Download
[webserver.py](https://raw.githubusercontent.com/sedlacek-modules/webserver/master/webserver.py)

## Features

- Convenient bidirectional file transfer within ssh session.  
    - With open ssh tunnel **no need for additional ssh sessions**.  
    `ssh user@remote.host -R 9999:localhost:9999 ...`
- **Pure Python3**.
    - Only Python distribution modules in use.
    - **Python 3.6+** _(f-strings literals)_.
    - One source file - **easy copy & paste to get it up running**.
- **Supports streaming** upload _(chunked encoding)_.
    - Forces append to file mode
- Locking.
    - Only within the server process.
    - No timeout, waits indefinitely
    - **Record only locking** when streamed upload.
        - Multiple sources/connections can append safely to same file.
        - Keeps record order as they arrive.
            ```
            server1# tail -f /var/log/nginx/acces.log | curl --upload-file - http://localhost:9999/colected.log
            --------
            server2# tail -f /var/log/nginx/acces.log | curl --upload-file - http://localhost:9999/colected.log
            ```
- Caution with large files.
    - Whole upload is read into memory. Or whole chunk.
- Directory listing.
    - text/plain when `User-Agent` start with `curl` or `wget`


## Examples
to serve `www` on `127.0.0.1:9999`
```
python3 webserver.py www
```
download file `www/aaa`
```
curl http://127.0.0.1:9999/aaa
```
upload file to `www/subdir/bbb`
```
curl --upload-file /etc/passwd http://127.0.0.1:9999/subdir/bbb
```
append file to `www/subdir/bbb`
```
curl -H 'Transfer-Encoding: chunked' --upload-file /etc/passwd http://127.0.0.1:9999/subdir/bbb
```
alternative for appending file to `www/subdir/bbb`
```
cat /etc/passwd | curl --upload-file - http://127.0.0.1:9999/subdir/bbb
```
stream updates
```
tail -f /var/log/syslog | curl --upload-file - http://127.0.0.1:9999/subdir/bbb
```
list content of `www` directory
```
curl http://127.0.0.1:9999/
```

## Help:
```
usage: webserver.py [-h] [--level {ERROR,INFO,DEBUG}] [--listen LISTEN]
                    [--port PORT]
                    [root]

Simple webserver with upload

positional arguments:
  root

optional arguments:
  -h, --help            show this help message and exit
  --level {ERROR,INFO,DEBUG}
                        Debug level
  --listen LISTEN       Listen address
  --port PORT           Listen port

EXAMPLE: curl --upload-file /etc/passwd http://localhost:9999/passwd
```