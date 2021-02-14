# Simple python3 webserver with upload
_Licensed under BSD3 license_ 

_Copyright (c) 2021, Ing. Jaromir Sedlacek_  
_All rights reserved._


##Features

- Convenient bidirectional file transfer within ssh session.  
    - With open ssh tunnel **no need for additional ssh sessions**.  
    `ssh user@remote.host -R 9999:localhost:9999 ...`
- **Pure Python3**.
    - Only Python distribution modules in use.
    - **Python 3.6+** _(f-strings literals)_.
- One source file - **easy copy & paste to get it up running**.
- **Support streaming** upload _(chunked encoding)_.
- Locking.
    - Only within the server process.
    - No timeout, waits indefinitely.
    - File locking.
        - `http://.../dir/file?nolock` will turn it off.
    - **Record locking** when streamed upload.
        - Cannot be turned off.
        - Multiple sources/connections can append safely to same file.
        - Keeps record order as they arrive.
            ```
            server1# tail -f /var/log/nginx/acces.log | curl --upload-file - "http://localhost:9999/colected.log?append"
            --------
            server2# tail -f /var/log/nginx/acces.log | curl --upload-file - "http://localhost:9999/colected.log?append"
            ```
- Caution with large files.
    - Whole upload is read into memory. Or whole chunk.
- Supports any combination of flags.
    - `http://.../dir/file?overwrite,append,flush,nolock`
    - `http://.../dir/file?overwrite&append&flush&nolock`  
      _same behavior, more difficult to type `&`_


## Examples
to serve `www` on `127.0.0.1:9999`
```
python3 webserver.py www
```
download file `www/aaa`
```
curl "http://127.0.0.1:9999/aaa"
```
upload file to `www/subdir/bbb`
```
curl --upload-file /etc/passwd "http://127.0.0.1:9999/subdir/bbb"
```
ensure overwrite of `www/subdir/bbb`
```
curl --upload-file /etc/passwd "http://127.0.0.1:9999/subdir/bbb?overwrite"
```
append file to `www/subdir/bbb`
```
date | curl --upload-file /etc/passwd "http://127.0.0.1:9999/subdir/bbb?append"
```
flush after each chunk _(append turn it on)_  
this allows `tail -f www/subdir/bbb` on server side to work nicely
```
while :; do date; sleep 10; done | curl --upload-file /etc/passwd "http://127.0.0.1:9999/subdir/bbb?append&flush"
```
list content of `www` directory (html output only)
```
curl "http://127.0.0.1:9999/"
```

### Help:
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