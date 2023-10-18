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
from prometheus_client import start_http_server, Summary, Enum, Info, Gauge

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

    if not stream_id:
        logging.info("Stream ID not sent.")
        return False

    Subscribe(stream_id, 'intf')
    Subscribe(stream_id, 'nw_inst')
    Subscribe(stream_id, 'lldp')
    Subscribe(stream_id, 'route')
    Subscribe(stream_id, 'cfg')

def get_app_id(app_name):

    logging.info(f'Metadata {metadata} ')
    appId_req = AppIdRequest(name=app_name)
    app_id_response=stub.GetAppId(request=appId_req, metadata=metadata)
    logging.info(f'app_id_response {app_id_response.status} {app_id_response.id} ')
    
    return app_id_response.id

def sanitize_for_prometheus(s):
    
    sanitized = re.sub(r'[^a-zA-Z0-9_:]', '_', s)
    sanitized = sanitized.strip('_')
    if not sanitized:
        sanitized = 'invalid'
    
    return sanitized

declared_enums = {}
declared_info = []
current_neighbors = {}
lldp_neighbors_gauge = Gauge(
    'lldp_neighbors',
    'Tracks LLDP neighbors',
    ['interface_name', 'system_name']
)

def handle_InterfaceNotification(notification: Notification) -> None:
    
    enum_name = 'admin_state_' + sanitize_for_prometheus(notification.key.if_name) + "_" + socket.gethostname()
    if enum_name in declared_enums:
        if notification.data.admin_is_up == 1:
            declared_enums[enum_name].state('up')
        else:
            declared_enums[enum_name].state('down')
    else:
        admin_state = Enum(enum_name, 'interface admin_state', states=['up', 'down'])
        if notification.data.admin_is_up == 1:
            admin_state.state('up')
        else:
            admin_state.state('down')
        
        declared_enums[enum_name] = admin_state

def handle_LldpNeighborNotification(notification: Notification) -> None:

    interface_name = str(notification.key.interface_name)
    system_name = str(notification.data.system_name)
    
    if notification.op != "Delete":
        lldp_neighbors_gauge.labels(interface_name=interface_name, system_name=system_name).set(1)
    else:
        lldp_neighbors_gauge.labels(interface_name=interface_name, system_name=system_name).set(0)

    

def handle_NetworkInstanceNotification(notification: Notification) -> None:

    enum_name = 'nwinst_state_' + sanitize_for_prometheus(notification.key.inst_name) + "_" + socket.gethostname()

    if enum_name in declared_enums:
        if str(notification.data.oper_is_up) == "True":
            declared_enums[enum_name].state('up')
        else:
            declared_enums[enum_name].state('down')
    else:
        admin_state = Enum(enum_name, 'nw_instance oper_state', states=['up', 'down'])
        if str(notification.data.oper_is_up) == "True":
            admin_state.state('up')
        else:
            admin_state.state('down')
        
        declared_enums[enum_name] = admin_state

def Handle_Notification(notification: Notification)-> None:
    if notification.HasField("config"):
        #handle_ConfigNotification(notification.config)
        logging.info("Implement config notification handling if needed")
    if notification.HasField("intf"):
        handle_InterfaceNotification(notification.intf)
    if notification.HasField("nw_inst"):
        handle_NetworkInstanceNotification(notification.nw_inst)
    if notification.HasField("lldp_neighbor"):
        handle_LldpNeighborNotification(notification.lldp_neighbor)
    if notification.HasField("route"):
        #handle_IpRouteNotification(notification.route)
        logging.info("Implement route notification handling if needed")

    return False

def Run():    

    ns_path = '/var/run/netns/srbase-mgmt'
    ns_fd = os.open(ns_path, os.O_RDONLY)

    libc = ctypes.CDLL('libc.so.6')
    setns = libc.setns
    setns.argtypes = [ctypes.c_int, ctypes.c_int]

    CLONE_NEWNET = 0x40000000

    if setns(ns_fd, CLONE_NEWNET) == -1:
        raise Exception("Failed to set network namespace")

    start_http_server(8000)

    sub_stub = SdkNotificationServiceStub(channel)
    response = stub.AgentRegister(request=AgentRegistrationRequest(), metadata=metadata)
    logging.info(f"Registration response : {response.status}")
            
    app_id = get_app_id(agent_name)
    if not app_id:
        logging.error(f'idb does not have the appId for {agent_name} : {app_id}')
    else:
        logging.info(f'Got appId {app_id} for {agent_name}')

    request = NotificationRegisterRequest(op=NotificationRegisterRequest.Create)
    create_subscription_response = stub.NotificationRegister(request=request, metadata=metadata)
    stream_id = create_subscription_response.stream_id

    logging.info(f"Create subscription response received. stream_id : {stream_id}")

    Subscribe_Notifications(stream_id)

    stream_request = NotificationStreamRequest(stream_id=stream_id)
    stream_response = sub_stub.NotificationStream(stream_request, metadata=metadata)
    count = 0
    while True:
        try:
            for r in stream_response:
                count += 1
                logging.info(f"Count :: {count}  NOTIFICATION:: \n{r.notification}")
                for obj in r.notification:
                    Handle_Notification(obj)
        except grpc._channel._Rendezvous as err:
            logging.info('GOING TO EXIT NOW: {}'.format(str(err)))
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
    stdout_dir = '/var/log/srlinux/stdout'
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
