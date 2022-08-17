# """ Sample implementation of an RTMP server. """
#
# import pyamf.util
# import rtmp_protocol_base
# import rtmp_protocol
# import SocketServer
# import time
#
# class RTMPHandler(SocketServer.BaseRequestHandler):
#     """ Handles a client connection. """
#
#     WAITING_C1 = 0
#     WAITING_C2 = 1
#     WAITING_COMMAND_CONNECT = 2
#     WAITING_DATA = 3
#
#     def handle(self):
#         """
#         This method gets called when a client connects to the RTMP server. It
#         implements a state machine.
#         """
#         state = self.WAITING_C1
#         self.state2 = 0
#         f = self.request.makefile()
#         self.sock_stream = rtmp_protocol.FileDataTypeMixIn(f)
#         self.reader = rtmp_protocol.RtmpReader(self.sock_stream)
#         self.writer = rtmp_protocol.RtmpWriter(self.sock_stream)
#
#         while True:
#             if state == self.WAITING_C1:
#                 self.handle_C1()
#                 state += 1
#             elif state == self.WAITING_C2:
#                 self.handle_C2()
#                 state += 1
#             elif state == self.WAITING_COMMAND_CONNECT:
#                 self.handle_command_connect()
#                 state += 1
#             elif state == self.WAITING_DATA:
#                 self.handle_data()
#             else:
#                 assert False, state
#
#     def handle_C1(self):
#         """
#         Handle version byte and first handshake packet sent by client. Send
#         version byte and two handshake packets to client.
#         """
#         self.sock_stream.read_uchar()
#         c1 = rtmp_protocol_base.Packet()
#         c1.decode(self.sock_stream)
#
#         self.sock_stream.write_uchar(3)
#         s1 = rtmp_protocol_base.Packet(first=0,second=0,payload='x'*1528)
#         s1.encode(self.sock_stream)
#         s2 = rtmp_protocol_base.Packet(first=0,second=0,payload='x'*1528)
#         s2.encode(self.sock_stream)
#         self.sock_stream.flush()
#
#     def handle_C2(self):
#         """ Handle second handshake packet from client. """
#         c2 = rtmp_protocol_base.Packet()
#         c2.decode(self.sock_stream)
#
#     def handle_command_connect(self):
#         """ Handle the first RTMP message that initiates the connection. """
#         self.reader.next()
#         msg = {
#             'msg': rtmp_protocol.DataTypes.COMMAND,
#             'command':
#             [
#                 u'_result',
#                 1,
#                 {'capabilities': 31, 'fmsVer': u'FMS/3,0,2,217'},
#                 {
#                     'code': u'NetConnection.Connect.Success',
#                     'objectEncoding': 0,
#                     'description': u'Connection succeeded.',
#                     'level': u'status'
#                 }
#             ]
#         }
#         self.writer.write(msg)
#         self.writer.flush()
#
#     def handle_data(self):
#         """
#         Handle additional RTMP messages from the client. In this sample
#         implementation the server waits for 2 shared object use events and
#         responds with the use_success, clear and change events for each one of
#         them.
#         """
#
#         msg = {
#             'msg': rtmp_protocol.DataTypes.SHARED_OBJECT,
#             'curr_version': 0,
#             'flags': '\x00\x00\x00\x00\x00\x00\x00\x00',
#             'events':
#             [
#                 {
#                     'type':rtmp_protocol.SOEventTypes.USE_SUCCESS,
#                     'data':''
#                 },
#                 {
#                     'type':rtmp_protocol.SOEventTypes.CLEAR,
#                     'data':''
#                 },
#                 {
#                     'type': rtmp_protocol.SOEventTypes.CHANGE,
#                 }
#             ]
#         }
#
#         if self.state2 == 0:
#             self.state2 += 1
#             print self.reader.next()
#             time.sleep(2)
#             msg['obj_name'] = 'so_name'
#             msg['events'][2]['data'] = {'sparam':'1234567890 '*5}
#             self.writer.write(msg)
#             self.writer.flush()
#         elif self.state2 == 1:
#             self.state2 += 1
#             print self.reader.next()
#             time.sleep(2)
#             msg['obj_name'] = 'so2_name'
#             msg['events'][2]['data'] = {'sparam':'QWERTY '*20}
#             self.writer.write(msg)
#             self.writer.flush()
#         else:
#             print self.reader.next()
#
# def main():
#     """ Start the RTMP server on 127.0.0.1 at port 80. """
#     server = SocketServer.TCPServer(('127.0.0.1', 80), RTMPHandler)
#     server.serve_forever()
#
# if __name__ == '__main__':
#     main()
