#!/usr/bin/env python
# coding=utf-8

from unittest import result
import grpc
import datetime
import time
import sys
import logging
import socket
import random
import os
import ctypes
import ipaddress
import json
import signal
import subprocess
import threading
import queue
import re
from logging.handlers import RotatingFileHandler
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
from prometheus_client import start_http_server, Summary
#from pygnmi.client import gNMIclient,telemetryParser

#import sdk_service_pb2
#import sdk_service_pb2_grpc
#import config_service_pb2
#import telemetry_service_pb2
#import telemetry_service_pb2_grpc
#import sdk_common_pb2
#from logger import *
#from element import *
#from target import *


agent_name ='srtelemetry'
channel = grpc.insecure_channel('localhost:50053')
metadata = [('agent_name', agent_name)]
stub = SdkMgrServiceStub(channel)

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
    logging.info('Status of subscription response for {}:: {}'.format(option, subscription_response.status))

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


def Handle_Notification(notification: Notification)-> None:
    logging.info("Handling notifications NOW")
    # Field names are available on the Notification documentation page
    if notification.HasField("config"):
        logging.info("CONFIG")
        #handle_ConfigNotification(notification.config)
    if notification.HasField("intf"):
        logging.info("INTF")
        #handle_InterfaceNotification(notification.intf)
    if notification.HasField("nw_inst"):
        logging.info("NWINST")
        #handle_NetworkInstanceNotification(notification.nw_inst)
    if notification.HasField("lldp_neighbor"):
        logging.info("LLDP")
        #handle_LldpNeighborNotification(notification.lldp_neighbor)
    if notification.HasField("bfd_session"):
        logging.info("BFD")
        #handle_BfdSessionNotification(notification.bfd_session)
    if notification.HasField("route"):
        logging.info("ROUTE")
        #handle_IpRouteNotification(notification.route)
    if notification.HasField("appid"):
        logging.info("APPID")
        #handle_AppIdentNotification(notification.appid)
    if notification.HasField("nhg"):
        logging.info("NHG")
        #handle_NextHopGroupNotification(notification.nhg)
    return False

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')

# Decorate function with metric.
@REQUEST_TIME.time()
def process_request(t):
    """A dummy function that takes some time."""
    time.sleep(t)

def Run():    

    # Path to your network namespace
    ns_path = '/var/run/netns/srbase-mgmt'

    # Open the file corresponding to the network namespace
    ns_fd = os.open(ns_path, os.O_RDONLY)

    # Load the setns function
    libc = ctypes.CDLL('libc.so.6')
    setns = libc.setns
    setns.argtypes = [ctypes.c_int, ctypes.c_int]

    # CLONE_NEWNET constant for network namespace
    CLONE_NEWNET = 0x40000000

    # Set the network namespace
    if setns(ns_fd, CLONE_NEWNET) == -1:
        raise Exception("Failed to set network namespace")

    # Start the HTTP server
    start_http_server(8000)

    process_request(random.random())

    sub_stub = SdkNotificationServiceStub(channel)

    response = stub.AgentRegister(request=AgentRegistrationRequest(), metadata=metadata)
    logging.info(f"Registration response : {response.status}")

        
            
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
    count = 0
    route_count = 0
    while True:
        try:
            for r in stream_response:
                count += 1
                logging.info(f"Count :: {count}  NOTIFICATION:: \n{r.notification}")
                for obj in r.notification:
                    logging.info("ITERATING THROUGH NOTIFICATION")
                    #if obj.HasField('config') and obj.config.key.js_path == ".commit.end":
                        #logging.info('TO DO -commit.end config')
                        #Create new handler to subscribe to telemetry notifications if config adds any topology element
                        #Possibly use pygnmi to subscribe telemetry paths
                    #else:
                    Handle_Notification(obj)
        except grpc._channel._Rendezvous as err:
            logging.info('GOING TO EXIT NOW: {}'.format(str(err)))
            #print("Rendezvous Exception")
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

        #    return True
        #sys.exit()
        #return True

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
    stdout_dir = '/var/log/srlinux/stdout' # PyTEnv.SR  L_STDOUT_DIR
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
