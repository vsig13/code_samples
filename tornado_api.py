#!/usr/bin/env python3

#
# API handler example using Tornado server
#

import sys
import subprocess

import tornado
from tornado import web, websocket
from tornado.ioloop import IOLoop
from tornado.options import define, options

import models


define('port', default=8000, help='run on given port', type=int)


class WebSocketHandler(websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        print('---> WS Open')
        if self not in cl:
            cl.append(self)

    def on_message(self, message):
        print('---> On message', message)
        # msg = json_util.loads(message)

    def on_close(self):
        if self in cl:
            cl.remove(self)


class RequestHandler(web.RequestHandler):
    def set_default_headers(self):
        super(RequestHandler, self).set_default_headers()

    def set_json_headers(self):
        self.set_header('Content-Type', 'application/json')


class APIHandler(RequestHandler):
    @tornado.web.asynchronous
    async def delete(self, uid, fmt=None):
        """Delete object by its id
        """
        try:
            entity = models.Entity.objects(id=uid).get()
            entity.delete()
        except:
            self.set_status(404)

    @tornado.web.asynchronous
    async def get(self, object_name, uid, fmt):
        """Retrieve object or collection.
        If fmt is not 'json', render form. Return json data otherwise.
        """
        entity = getattr(models, object_name)

        # Return a collection if no uid was passed.
        # If uid is a valid object id, edit form is displayed or
        # serialized object as json, depending on fmt
        if uid is None:
            form_edit = False
            data = entity.objects.all()
        else:
            form_edit = True
            data = entity.objects(id=uid).get()

        if fmt is None:
            if uid is None:
                form = models.EntityForm()
            else:
                form = models.EntityForm(None, data)
                form.populate_obj(data)

            self.render('form_entity.html',
                        entities=data,
                        form=form,
                        uid=uid,
                        form_edit=form_edit,
                        legend='Edit entity')
        else:
            self.set_json_headers()
            self.write(data.to_json())

    @tornado.web.asynchronous
    async def patch(self, *args, **kwargs):
        """Modify an existing object
        Basically, post with uid required
        """
        if 'uid' in kwargs:
            return self.post(*args, **kwargs)
        else:
            self.set_status(400)
            self.set_json_headers()
            self.write(dict(errors=['uid is required']))

    @tornado.web.asynchronous
    async def post(self, uid, fmt=None):
        """Create or modify an object
        """
        response = {'json_response': 'json response data'}
        self.set_json_headers()

        if uid is not None:
            entity = models.Entity.objects(id=uid).get()
        else:
            entity = models.Entity()

        form = models.EntityForm(self.request.arguments, id=uid)

        if self.request.arguments and form.validate():
            # form.populate_obj(entity)
            entity.save()
            response['errors'] = False
        else:
            self.set_status(400)
            response['errors'] = form.errors
        self.write(response)
        self.finish()


class Application(web.Application):
    def __init__(self):
        _settings = dict(
            debug=True,
            autoreload=True,
            compress_response=True,
            cookie_secret='k0xCrT/TzXQ2JOLYo7a3XbgRDMn92MnbI8QzNtraZAnnnT2qWppLHL+2f+mgyk1iZ3w=',
            template_path='templates'
        )

        urls = (
            (r'/(?P<object_name>\w+?)(?:\/(?P<uid>\w+)/?)?(?P<fmt>\.json)?[#]?/?$',
             APIHandler
            ),
            (r'^/ws/?', WebSocketHandler),
            (r'/static/(.*)?', tornado.web.StaticFileHandler,
             {'path': STATIC_PATH}
            ),
        )
        web.Application.__init__(self, urls, **_settings)


def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)

    io_loop = IOLoop.current()
    io_loop.start()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
