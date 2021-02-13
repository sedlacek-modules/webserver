# Simple python3 webserver with upload
_Licensed under BSD3 license_ 

_Copyright (c) 2021, Ing. Jaromir Sedlacek_  
_All rights reserved._

##Features
- **Not for production use**  
    &nbsp;&nbsp;&nbsp;&nbsp;_I use it just for more convenient file transfer within the ssh session with open tunnel (without need for additional ssh sessions)_  
    &nbsp;&nbsp;&nbsp;&nbsp;`ssh user@remote.host -R 9999:localhost:999 ...`
- Only pure python3 standard modules from distribution, no need to install anything else
- Contained only in one file - **easy copy & paste to get it running**
- Support streaming upload from multiple sources
- Locking (only within server), no timeout, waits indefinitely
    - Record locking when streamed (chunked) upload
        ```
        server1# tail -f /var/log/nginx/acces.log | curl --upload-file - "http://localhost:9999/colected.log?append"
        ```
        ```
        server2# tail -f /var/log/nginx/acces.log | curl --upload-file - "http://localhost:9999/colected.log?append"
        ```
        - Should keep records in order as they came
        - Cannot be turned off
    - Whole file locking, otherwise
    - Use `http://.../dir/file?nolock` to turn off whole file locking
- Whole upload is read into memory (caution with large file uploads)
    - or whole chunk for chunked encoding
- Tested with Python 3.9.0, but should work with any Python 3.6+ (f-strings literals)
- Supports any combination `http://.../dir/file?overwrite,append,flush,nolock`
    - `http://.../dir/file?overwrite&append&flush&nolock`  
      _same behavior, just more difficult to type_


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