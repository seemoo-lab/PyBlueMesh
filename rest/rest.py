import Pyro4
import logging
from tpynode import TPyModule

import bottle
from bottle import Bottle, ServerAdapter
from bottle import route, run, template
from paste import httpserver
from wsgiref.simple_server import WSGIRequestHandler

from threading import Thread, Lock, Condition
import time
import subprocess


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Logger for multithreading
lock = Lock()
rest_object = None

 
class MyWSGIRefServer(ServerAdapter):

# Server class that holds multithreaded server instance.

    def __init__(self, condition, **kwargs):
        super(MyWSGIRefServer, self).__init__(**kwargs)
        self.rest_socket = None 
        
        # condition = The condition that handles the stop request for the server.
        self.condition = condition 
 
    def run(self, handler):
        while True:
            with self.condition:
                if self.quiet:
                    class QuietHandler(WSGIRequestHandler):
                        def log_request(*args, **kw): pass
                lock.acquire()

                # Create the multithreaded server instance. daemon_threads must be True otherwise the threads
                # are not closed when the node is stopped.
                self.rest_socket = httpserver.serve(bottle.default_app(), host = self.host, port = self.port, 
                                                    start_loop=False, daemon_threads=True, use_threadpool=True, 
                                                    threadpool_workers=5)
                logger.info('Rest server created.')  
                lock.release()
                if self.rest_socket is not None:
                    # Starts the server connections.
                    self.rest_socket.serve_forever()
                    # Wait for a stop request that terminates the Rest server thread.
                    self.condition.wait()
                    break
    def stop(self):
        logger.info('Rest server stop requested')
        #self.rest_socket.shutdown()
        self.rest_socket.server_close()

    def serve_forever(self):
        while True:
            # waits for incoming connections.
            self.rest_socket.serve_forever()

class REST(TPyModule):

    def __init__(self, **kwargs):
        super(REST, self).__init__(**kwargs)
        
        # Set the port of the Rest server.
        self._port = int(kwargs.get('port'))

        # Set debug mode on or off. 
        self._debug = bool(kwargs.get('debug'))
        
        # Set autostart of the Rest API.
        self._autostart = bool(kwargs.get('autostart'))

        global rest_object
        rest_object = self

        # Stop condition for the server thread.
        self.stop_condition = Condition()

        # Define app instance and server instance at startup.
        self.app = bottle.default_app()
        self.server = MyWSGIRefServer(condition = self.stop_condition,host='0.0.0.0', port=str(self._port))

        if self._autostart:
            self.start()
  
    @Pyro4.expose
    def start(self):
        try:
            # Create a server thread for the rest server that can be terminated.
            self.rest_thread = Thread(target=self.app.run,kwargs=dict(server = self.server, debug = True))
            self.rest_thread.daemon = True
            self.rest_thread.start()

            # Wait until server is created.
            time.sleep(0.5)
            
            logger.info('Rest API successfully (re)started on port: ' + str(self._port))
        except Exception as ex:
            logger.info('Rest API could not be started: ' + str(ex))
 
    @Pyro4.expose 
    def stop(self):
        try:
            # Stop the server socket.
            self.server.stop()

            # Close the server thread.
            if self.rest_thread.is_alive():
                self.stop_condition.acquire()
                self.stop_condition.notify()
                self.stop_condition.release()
            logger.info('Rest API successfully stopped!')
        except Exception as ex:
            logger.info('Rest API could not be stopped:' + str(ex))
            return ex
              
  
    @Pyro4.expose
    def restart(self):
        try:
            self.stop()
            self.start()
        except Exception as ex:
            logger.info('Rest API could not be restarted:' + str(ex))


    @route('/rest/stop','GET')
    def rest_stop():
        # Get the rest object from a global variable 
        # during a rest call of the method.
        global rest_object
        self = rest_object
        t = Thread(target = self.stop(), daemon = False)
        return 'Rest API successfully stopped!'
        t.start()


    @route('/rest/restart','GET')
    def rest_restart():
        # Get the rest object from a global variable 
        # during a rest call of the method.
        global rest_object
        self = rest_object
        t = Thread(target = self.restart, daemon = False)
        t.start()
        return 'Rest API successfully restarted!'

    @route('/test')    
    def getTest():        
        return "Test was successfull!" 
