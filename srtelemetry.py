#!/usr/bin/env python
# coding=utf-8

from unittest import result
import grpc
import datetime
import time
import sys
import logging
import socket
import os
import ipaddress
import json
import signal
import subprocess
import threading
import queue
import re
from logging.handlers import RotatingFileHandler


#import sdk_service_pb2
#import sdk_service_pb2_grpc
#import config_service_pb2
#import telemetry_service_pb2
#import telemetry_service_pb2_grpc
#import sdk_common_pb2
from ndk import appid_service_pb2
from ndk.sdk_service_pb2_grpc import SdkMgrServiceStub
from ndk.sdk_service_pb2_grpc import SdkNotificationServiceStub
from ndk.sdk_service_pb2 import AgentRegistrationRequest
from ndk.sdk_common_pb2 import SdkMgrStatus
from ndk.sdk_service_pb2 import NotificationRegisterRequest
from ndk.sdk_service_pb2 import NotificationStreamRequest
from ndk.sdk_service_pb2 import Notification
from ndk.sdk_service_pb2 import AppIdRequest
from ndk import interface_service_pb2
from ndk import networkinstance_service_pb2
from ndk import lldp_service_pb2
from ndk import route_service_pb2
from ndk import config_service_pb2


from ndk.config_service_pb2 import ConfigSubscriptionRequest




#from logger import *
#from element import *
#from target import *

# Modules
from pygnmi.client import gNMIclient,telemetryParser
############################################################
#                       Variables
############################################################

############################################################
## Agent will start with this name
############################################################
agent_name ='srtelemetry'

############################################################
## FILENAME of input
############################################################
#FILENAME = 'input_elements'
# This file is only used in Guilherme's implementation

############################################################
## Open a GRPC channel to connect to sdk_mgr on the dut
## sdk_mgr will be listening on 50053
############################################################
channel = grpc.insecure_channel('localhost:50053')
metadata = [('agent_name', agent_name)]
stub = SdkMgrServiceStub(channel)

############################################################
## This is the Global Variables to the srtelemetry to work 
############################################################
# GNMI Server
##host = ('unix:///opt/srlinux/var/run/sr_gnmi_server', 57400)

# Main Variables of the agent
global_paths = []
targets = []
elements = []

""" def handle_notification(notification: Notification) -> None:
    # Field names are available on the Notification documentation page
    if notification.HasField("config"):
        #handle_ConfigNotification(notification.config)
        print(notification.config)
    if notification.HasField("intf"):
        #handle_InterfaceNotification(notification.intf)
        print(notification.intf)
    if notification.HasField("nw_inst"):
        #handle_NetworkInstanceNotification(notification.nw_inst)
        print(notification.nw_inst)
    if notification.HasField("lldp_neighbor"):
        #handle_LldpNeighborNotification(notification.lldp_neighbor)
        print(notification.lldp_neighbor)
    if notification.HasField("bfd_session"):
        #handle_BfdSessionNotification(notification.bfd_session)
        print(notification.bfd_session)
    if notification.HasField("route"):
        #handle_IpRouteNotification(notification.route)
        print(notification.route)
    if notification.HasField("appid"):
        #handle_AppIdentNotification(notification.appid)
        print(notification.appid)
    if notification.HasField("nhg"):
        #handle_NextHopGroupNotification(notification.nhg)
        print(notification.nhg)

sdk_mgr_client = SdkMgrServiceStub(channel)

register_request = AgentRegistrationRequest()
register_request.agent_liveliness = 5 # Optional
response = sdk_mgr_client.AgentRegister(request=register_request, metadata=metadata)
print(response)
if response.status == SdkMgrStatus.kSdkMgrSuccess:
    # Agent has been registered successfully
    print("Success")
    pass
else:
    print("Registration ERROR")
    # Agent registration failed error string available as response.error_str
    pass


request = NotificationRegisterRequest(op=NotificationRegisterRequest.Create)
response = sdk_mgr_client.NotificationRegister(request=request, metadata=metadata)
if response.status == SdkMgrStatus.kSdkMgrSuccess:
    # Notification Register successful
    stream_id = response.stream_id
    #print("stream id:"+str(stream_id))
    pass
else:
    # Notification Register failed, error string available as response.error_str
    pass



request = NotificationRegisterRequest(
    stream_id=stream_id,
    op=NotificationRegisterRequest.AddSubscription,
    config=ConfigSubscriptionRequest(),
)

response = sdk_mgr_client.NotificationRegister(request=request, metadata=metadata)
if response.status == SdkMgrStatus.kSdkMgrSuccess:
    # Successful registration
    print(response.status)
    pass
else:
    # Registration failed, error string available as response.error_str
    pass

sdk_notification_client = SdkNotificationServiceStub(channel)
stream_request = NotificationStreamRequest(stream_id=stream_id)
stream_response = sdk_notification_client.NotificationStream(
    request=stream_request, metadata=metadata
)

try:
    for response in stream_response:
        for notification in response.notification:
            # Handle notifications
            print(notification)
            handle_notification(notification)
            pass

except grpc._channel._Rendezvous as err:
            print('GOING TO EXIT NOW: {}'.format(err))
            sys.exit()
 """

def Subscribe(stream_id, option):
    op = NotificationRegisterRequest.AddSubscription
    if option == 'intf':
        entry = interface_service_pb2.InterfaceSubscriptionRequest()
        request = NotificationRegisterRequest(op=op, stream_id=stream_id, intf=entry)
    elif option == 'nw_inst':
        entry = networkinstance_service_pb2.NetworkInstanceSubscriptionRequest()
        request = NotificationRegisterRequest(op=op, stream_id=stream_id, nw_inst=entry)
    elif option == 'lldp':
        entry = lldp_service_pb2.LldpNeighborSubscriptionRequest()
        request = NotificationRegisterRequest(op=op, stream_id=stream_id, lldp_neighbor=entry)
    elif option == 'route':
        entry = route_service_pb2.IpRouteSubscriptionRequest()
        request = NotificationRegisterRequest(op=op, stream_id=stream_id, route=entry)
    elif option == 'cfg':
        entry = config_service_pb2.ConfigSubscriptionRequest()
        request = NotificationRegisterRequest(op=op, stream_id=stream_id, config=entry)

    subscription_response = stub.NotificationRegister(request=request, metadata=metadata)
    print('Status of subscription response for {}:: {}'.format(option, subscription_response.status))

def Subscribe_Notifications(stream_id):
    '''
    Agent will receive notifications to what is subscribed here.
    '''
    if not stream_id:
        logging.info("Stream ID not sent.")
        return False

    ##Subscribe to Interface Notifications
    Subscribe(stream_id, 'intf')
    
    ##Subscribe to Network-Instance Notifications
    Subscribe(stream_id, 'nw_inst')

    ##Subscribe to LLDP Neighbor Notifications
    Subscribe(stream_id, 'lldp')

    ##Subscribe to IP Route Notifications
    Subscribe(stream_id, 'route')

    ##Subscribe to Config Notifications - configs added by the fib-agent
    Subscribe(stream_id, 'cfg')

def get_app_id(app_name):
    logging.info(f'Metadata {metadata} ')
    appId_req = AppIdRequest(name=app_name)
    app_id_response=stub.GetAppId(request=appId_req, metadata=metadata)
    logging.info(f'app_id_response {app_id_response.status} {app_id_response.id} ')
    return app_id_response.id


def Handle_Notification(obj, app_id)-> bool:
    print("App_id"+str(app_id))
    return False



def Run():
    sub_stub = SdkNotificationServiceStub(channel)

    response = stub.AgentRegister(request=AgentRegistrationRequest(), metadata=metadata)
    logging.info(f"Registration response : {response.status}")
    
    app_id = get_app_id(agent_name)
    app_id = get_app_id(agent_name)
    if not app_id:
        logging.error(f'idb does not have the appId for {agent_name} : {app_id}')
    else:
        logging.info(f'Got appId {app_id} for {agent_name}')

    request=NotificationRegisterRequest(op=NotificationRegisterRequest.Create)
    create_subscription_response = stub.NotificationRegister(request=request, metadata=metadata)
    stream_id = create_subscription_response.stream_id
    logging.info(f"Create subscription response received. stream_id : {stream_id}")

    Subscribe_Notifications(stream_id)

    stream_request = NotificationStreamRequest(stream_id=stream_id)
    stream_response = sub_stub.NotificationStream(stream_request, metadata=metadata)
    count = 1
    route_count = 0
    try:
        for r in stream_response:
            logging.info(f"Count :: {count}  NOTIFICATION:: \n{r.notification}")
            count += 1
            for obj in r.notification:
                if obj.HasField('config') and obj.config.key.js_path == ".commit.end":
                    logging.info('TO DO -commit.end config')
                else:
                    Handle_Notification(obj, app_id)
    except grpc._channel._Rendezvous as err:
        logging.info('GOING TO EXIT NOW: {}'.format(str(err)))
        print("Rendezvous Exception")
    except Exception as e:
        logging.error('Exception caught :: {}'.format(str(e)))
        print("Generic Run Exception: "+e)

        try:
            response = stub.AgentUnRegister(request=AgentRegistrationRequest(), metadata=metadata)
            logging.error('Run try: Unregister response:: {}'.format(response))
        except grpc._channel._Rendezvous as err:
            logging.info('GOING TO EXIT NOW: {}'.format(str(err)))
            print("Unregister Run Exception")
            sys.exit()

        return True
    sys.exit()
    return True

def Exit_Gracefully(signum, frame):
    logging.info("Caught signal :: {}\n will unregister fib_agent".format(signum))
    try:
        response=stub.AgentUnRegister(request=AgentRegistrationRequest(), metadata=metadata)
        logging.error('try: Unregister response:: {}'.format(response))
        sys.exit()
    except grpc._channel._Rendezvous as err:
        logging.info('GOING TO EXIT NOW: {}'.format(err))
        sys.exit()

if __name__ == '__main__':
    hostname = socket.gethostname()
    stdout_dir = '/var/log/srlinux/stdout' # PyTEnv.SRL_STDOUT_DIR
    signal.signal(signal.SIGTERM, Exit_Gracefully)
    if not os.path.exists(stdout_dir):
        os.makedirs(stdout_dir, exist_ok=True)
    log_filename = '{}/{}_srtelemetry.log'.format(stdout_dir, hostname)
    logging.basicConfig(filename=log_filename, filemode='a',\
                        format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',\
                        datefmt='%H:%M:%S', level=logging.INFO)
    handler = RotatingFileHandler(log_filename, maxBytes=3000000,
                                  backupCount=5)
    logging.getLogger().addHandler(handler)
    logging.info("START TIME :: {}".format(datetime.datetime.now()))
    if Run():
        logging.info('Agent unregistered and agent routes withdrawed from dut')
    else:
        logging.info(f'Some exception caught, Check !')
