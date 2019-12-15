import cgi
import copy
import datetime
import email.utils
import html
import http.client
import io
import json
import mimetypes
import os
import posixpath
import re
import select
import shutil
import socket  # For gethostbyaddr()
import socketserver
import sys
import time
import urllib.parse
from functools import partial
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pymysql

# connect to database
user = input("Please input your mysql user name:")
password = input("Please input your mysql password:")
conn = pymysql.connect(host='localhost', user=user, passwd=password,
                       db='mysql', charset='utf8', port=3306)  # 默认为127.0.0.1本地主机
cur = conn.cursor(cursor=pymysql.cursors.DictCursor)
cur.excute("USE DanmuDB")


class myHTTPRequestHandler(SimpleHTTPRequestHandler):

    def send_head(self):
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        """
        pattern = re.compile(r'^danmu/\d+$')
        if pattern.match(self.path) != None:
            # TODO
            id_str = self.path[6:]
            # TODO 还要指定视频
            cur.excute('SELECT * FROM DANMUS WHERE id > "%s"') % (id_str)
            results = cur.fetchall()
            ans = ""
            for row in results:
                # TODO 需要根据数据库实际情况修正
                cur_json = json.dumps(row)
                ans += cur_json + '\n'

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "danmus")
            self.send_header("Content-Length", str(len(ans)))
            self.end_headers()
            return ans

        else:
            path = self.translate_path(self.path)
            f = None
            if os.path.isdir(path):
                parts = urllib.parse.urlsplit(self.path)
                if not parts.path.endswith('/'):
                    # redirect browser - doing basically what apache does
                    self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                    new_parts = (parts[0], parts[1], parts[2] + '/',
                                 parts[3], parts[4])
                    new_url = urllib.parse.urlunsplit(new_parts)
                    self.send_header("Location", new_url)
                    self.end_headers()
                    return None
                for index in "index.html", "index.htm":
                    index = os.path.join(path, index)
                    if os.path.exists(index):
                        path = index
                        break
                else:
                    return self.list_directory(path)
            ctype = self.guess_type(path)
            try:
                f = open(path, 'rb')
            except OSError:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return None

            try:
                fs = os.fstat(f.fileno())
                # Use browser cache if possible
                if ("If-Modified-Since" in self.headers
                        and "If-None-Match" not in self.headers):
                    # compare If-Modified-Since and time of last file modification
                    try:
                        ims = email.utils.parsedate_to_datetime(
                            self.headers["If-Modified-Since"])
                    except (TypeError, IndexError, OverflowError, ValueError):
                        # ignore ill-formed values
                        pass
                    else:
                        if ims.tzinfo is None:
                            # obsolete format with no timezone, cf.
                            # https://tools.ietf.org/html/rfc7231#section-7.1.1.1
                            ims = ims.replace(tzinfo=datetime.timezone.utc)
                        if ims.tzinfo is datetime.timezone.utc:
                            # compare to UTC datetime of last modification
                            last_modif = datetime.datetime.fromtimestamp(
                                fs.st_mtime, datetime.timezone.utc)
                            # remove microseconds, like in If-Modified-Since
                            last_modif = last_modif.replace(microsecond=0)

                            if last_modif <= ims:
                                self.send_response(HTTPStatus.NOT_MODIFIED)
                                self.end_headers()
                                f.close()
                                return None

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", ctype)
                self.send_header("Content-Length", str(fs[6]))
                self.send_header("Last-Modified",
                                 self.date_time_string(fs.st_mtime))
                self.end_headers()
                return f
            except:
                f.close()
                raise

    def do_POST(self):
        # TODO CGI needed
        content_length = int(self.headers['Content_Length'])
        body = self.rfile.read(content_length)
        body_str = body.decode('UTF-8', 'strict')
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        danmuData = json.loads(body_str)

        # TODO 需要根据数据库实际情况修正
        insert_sql = "INSERT INTO DANMUS () VALUES ('%s', '%s', '%s')" % (
            danmuData['content'], danmuData['size'], danmuData['color'])

        try:
            cur.excute(insert_sql)
            conn.commit()
        except:
            conn.rollback()


httpd = HTTPServer(('localhost', 9000), SimpleHTTPRequestHandler)
httpd.serve_forever()

conn.close()
