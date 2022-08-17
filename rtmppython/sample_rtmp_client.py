# """ Sample implementation of an RTMP client. """
#
# import rtmp_protocol
#
# class SO(rtmp_protocol.FlashSharedObject):
#     """ Represents a sample shared object. """
#
#     def on_change(self, key):
#         """ Handle change events for the specific shared object. """
#         print '%s.sparam = "%s"' % (self.name, self.data['sparam'])
#
# def main():
#     """
#     Start the client, connect to 127.0.0.1:80 and use 2 remote flash shared
#     objects.
#     """
#     client = rtmp_protocol.RtmpClient('127.0.0.1', 80, '', '', '', '')
#     client.connect([])
#
#     so_name = SO('so_name')
#     client.shared_object_use(so_name)
#
#     so2_name = SO('so2_name')
#     client.shared_object_use(so2_name)
#
#     client.handle_messages()
#
# if __name__ == '__main__':
#     main()
