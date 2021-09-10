
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
    Grid2Demand based on osm2gmns
    
    Author: Anjun Li, Southwest Jiaotong University
            Xuesong (Simon) Zhou, Arizona State University
            Entai Wang, Beijing Jiaotong University
            Taehooie Kim, Arizona State University

    Email:  anjun.li93@gmail.com
            xzhou74@asu.edu
            entaiwang@bjtu.edu.cn
            taehooie.kim@asu.edu
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

import os
import pandas as pd
import numpy as np
import math
import csv
import locale
import sys
from pprint import pprint
from collections import defaultdict
import logging
import random
from random import choice
import osm2gmns as og


class Node:
    def __init__(self):
        self.name = ''
        self.id = 0
        self.osm_node_id = ''
        self.osm_highway = ''
        self.zone_id = None
        # commments: default is 0, or no value; only four conditions for a node to become an activity node
        # and zone_id != 0: 1) POI node, 2) is_boundary node(freeway) 3) residential in activity_type 4) external POI
        self.ctrl_type = ''
        self.node_type = ''
        self.activity_type = ''  # commments: provided from osm2gmns such as motoway, residential, ...
        self.boundary_flag = 0  # comments: = 1 (current node is boundry node)
        self.x_coord = 0
        self.y_coord = 0
        self.main_node_id = ''
        self.poi_id = ''  # commments: default = None; to be assigned to a POI ID after reading poi.csv and customized_poi.csv
        # if current node is poi node
        self.notes = ''
        self.activity_zone_id = None
        self.production = 0 # commments: = 0 (current node is not poi node)
        self.attraction = 0 # commments: = 0 (current node is not poi node)
        self.activity_location_tab = ''
        self.activity_node_flag = ''


class POI:
    def __init__(self):
        self.name = ''
        self.id = 0
        self.osm_way_id = ''
        self.osm_relation_id = ''
        self.type = ''
        self.amenity = ''
        self.way = ''
        self.geometry = ''
        self.centroid = ''
        self.area = 0  # comments: total area of polygon for this poi zone
        self.area_ft2 = 0
        self.zone_id = 0 # comments: mapping from zone
        self.x_coord = 0
        self.y_coord = 0
        self.count = 1 # commments: total poi value for this poi node or poi zone
        self.nearest_node = None

# class OSM2GMNS_POI:
#     def __init__(self):
#         self.poi_id = 0
#         self.osm_way_id = None      # str
#         self.osm_relation_id = None
#         self.name = ''
#         self.geometry = None
#         self.geometry_xy = None
#         self.centroid = None
#         self.centroid_xy = None
#         self.nearest_node = None
#         self.building = None
#         self.amenity = None
#         self.way = None         # highway,railway,aeroway poi

class Zone: # comments: area of grid zone
    def __init__(self):
        self.id = 0
        self.name = '' # comments: internal No., such as A1, A2,...
        self.centroid_x = 0
        self.centroid_y = 0
        self.centroid = '' # comments: centroid coordinate (x, y) based on wkt format
        self.x_max = 0  # comments: boundary coordinate for this zone
        self.x_min = 0
        self.y_max = 0
        self.y_min = 0
        self.poi_count = 0 # comments: total poi counts in this zone
        self.residential_count = 0  # number of residential poi nodes in the zone
        self.office_count = 0  # number of office poi nodes in the zone
        self.shopping_count = 0  # number of shopping poi nodes in the zone
        self.school_count = 0  # number of school poi nodes in the zone
        self.parking_count = 0  # number of parking poi nodes in the zone
        self.boundary_count = 0  # number of boundary nodes in the zone
        self.node_id_list = [] # comments: nodes which belong to this zone
        self.poi_id_list = [] # comments: poi points which belong to this zone
        self.poi_node_list = []
        self.polygon = '' # comments: study area boundary based on wkt format

        self.connector_list = []
        self.centroid_node = None


class Agent:
    def __init__(self):
        """ the attribute of agent """
        self.agent_id = 0
        self.agent_type = ''  # comments: vehicle default
        self.o_zone_id = 0
        self.d_zone_id = 0
        self.o_node_id = 0 # comments: randomly selected from activity nodes of a zone
        self.d_node_id = 0
        self.path_node_seq_no_list = list() # comments: node id not node seq no
        self.path_link_seq_no_list = list()
        self.current_link_seq_no_in_path = 0 # comments: not used
        self.path_cost = 0
        self.b_generated = False
        self.b_complete_trip = False
        self.departure_time = ''

class Link:
    def __init__(self, link_id, from_node_id, to_node_id, link_type_name, link_type_id):
        """ the attribute of link """
        self.link_id = link_id
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.link_type_name = link_type_name
        self.link_type_id = link_type_id
        self.geometry = None


# create a logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

"""PART 1  READ INPUT NETWORK FILES"""
g_node_list = []
g_boundary_node_list = []
g_outside_boundary_node_list = [] # comments: nodes outside the study area
g_poi_list = []
g_extended_poi_list = []
g_external_poi_list = []
g_simplified_poi_list = []
g_simplified_link_list = []
g_poi_id_type_dict = {}
g_poi_id_area_dict = {}
g_outside_boundary_node_id_index = {}
g_output_folder = ''
g_node_id_to_node = {}
g_node_id_to_index = {}
g_poi_map = {}
g_average_latitude = 0
g_useful_linktype_set = {}
g_poi_id_to_node_id = {}
poi_existing_flag = 0

def ReadNetworkFiles(input_folder=None):
    global g_node_list
    global g_poi_list
    global g_extended_poi_list
    global g_poi_id_type_dict
    global g_poi_id_area_dict
    global g_output_folder
    global g_average_latitude
    global g_poi_id_to_node_id
    global poi_existing_flag

    # local_poi_list = []
    # local_node_list = []

    if input_folder:
        node_filepath = os.path.join(input_folder, 'node.csv')
        poi_filepath = os.path.join(input_folder, 'poi.csv')
        g_output_folder = input_folder
        logfile = os.path.join(g_output_folder, 'log.txt')
    else:
        node_filepath = 'node.csv'
        poi_filepath = 'poi.csv'
        logfile = 'log.txt'

    # create a handler to write the log file
    fh = logging.FileHandler(logfile, mode='w')
    fh.setLevel(logging.DEBUG)

    # create a handler to print out in console
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)

    # define output format
    formatter = logging.Formatter('%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add handler to logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.debug('Starting ReadNetworkFiles')
    local_encoding = locale.getdefaultlocale()
    with open(node_filepath, encoding=local_encoding[1]) as fp:
        reader = csv.DictReader(fp)
        exclude_boundary_node_index = 0
        poi_flag = 0
        log_flag = 0
        index = 0
        for line in reader:
            try:
                activity_location_tab = line['activity_location_tab']
            except:  # there is no 'activity_location_tab' for the initial network file
                activity_location_tab = None
            if activity_location_tab is None or activity_location_tab != 'customized':  # to avoid overwriting
                node = Node()
                node.name = line['name']
                node_id = line['node_id']
                if node_id:
                    node.id = int(node_id)
                    g_node_id_to_index[node.id] = index
                else:
                    # print('Error: node_id is not defined in node.csv, please check it!')
                    logger.error("node_id is not defined in node.csv, please check it!")
                    sys.exit(0)

                try:
                    osm_node_id = line['osm_node_id']
                    if osm_node_id:
                        node.osm_node_id = str(osm_node_id)
                except:
                    node.osm_node_id = None

                node.osm_highway = line['osm_highway']
                node.ctrl_type = line['ctrl_type']
                node.node_type = line['node_type']
                node.main_node_id = line['main_node_id']
                node.notes = line['notes']

                try:
                    activity_type = line['activity_type']
                    if activity_type:
                        node.activity_type = str(activity_type)
                        if node.activity_type == 'residential':
                            node.activity_location_tab = 'residential'
                            node.activity_node_flag = '1'
                        if node.activity_type == 'poi':
                            node.activity_location_tab = 'poi'
                            node.activity_node_flag = '1'
                        if node.activity_type == 'centroid node':
                            continue
                except:
                    node.activity_type = None

                x_coord = line['x_coord']
                if x_coord:
                    node.x_coord = round(float(x_coord),7)
                else:
                    # print('Error: x_coord is not defined in node.csv, please check it!')
                    logger.error("x_coord is not defined in node.csv, please check it!")
                    sys.exit(0)

                y_coord = line['y_coord']
                if y_coord:
                    node.y_coord = round(float(y_coord),7)
                else:
                    # print('Error: y_coord is not defined in node.csv, please check it!')
                    logger.error("y_coord is not defined in node.csv, please check it!")
                    sys.exit(0)

                try:
                    poi_id = line['poi_id']
                    if poi_id:
                        node.poi_id = str(poi_id)
                        g_poi_id_to_node_id[node.poi_id] = node.id
                        poi_flag = 1  # comments: = 1 if poi_id exists
                except:
                    logger.warning("poi_id is not defined. Please check it in node.csv.")

                try:
                    boundary_flag = line['is_boundary']
                    if boundary_flag:
                        node.boundary_flag = int(float(boundary_flag))
                        if node.boundary_flag == 1:
                            node.activity_location_tab = 'boundary'
                            node.activity_node_flag = '1'
                    else:
                        logger.info("is_boundary is not defined in node.csv. Default value is 0.")
                        node.boundary_flag = 0
                except:
                    logger.info("is_boundary is not defined in node.csv. Default value is 0.")
                    node.boundary_flag = 0

                g_node_id_to_node[node.id] = node
                g_node_list.append(node)
                # local_node_list.append(node)

                if node.boundary_flag == 1:
                    g_boundary_node_list.append(node)
                else:
                    g_outside_boundary_node_list.append(node) # comments: outside boundary node
                    g_outside_boundary_node_id_index[node.id] = exclude_boundary_node_index
                    exclude_boundary_node_index += 1

                index += 1

        if poi_flag == 0:
            if (log_flag == 0):
                print('Field poi_id is not in node.csv. Please check it!')
                logger.warning('Field poi_id is NOT defined in node.csv. Please check node.csv! It could lead to '
                               'empty demand volume and zero agent. Please ensure to POIs=True in osm2gmns: net = '
                               'og.getNetFromOSMFile')
                log_flag = 1

        try:
            g_latitude_list = [node.y_coord for node in g_node_list]
            g_average_latitude = sum(g_latitude_list) / len(g_latitude_list)
        except:
            g_average_latitude = 99
            print('Please check y_coord in node.csv!')
            logger.warning('Please check y_coord in node.csv!')
    print("Number of nodes = ", len(g_node_list))

    try:
        with open(poi_filepath, encoding=local_encoding[1]) as fp:
            reader = csv.DictReader(fp)
            for line in reader:
                poi = POI()
                poi.name = line['name']
                poi.osm_way_id = line['osm_way_id']
                poi.osm_relation_id = line['osm_relation_id']

                poi_id = line['poi_id']
                if poi_id:
                    poi.id = int(poi_id)
                else:
                    logger.error("poi_id is not defined in poi.csv, please check it!")
                    sys.exit(0)

                centroid = line['centroid']
                poi.centroid = centroid
                if centroid:
                    temp_centroid = str(centroid)
                else:
                    # print('Error: centroid is not defined in poi.csv, please check it!')
                    logger.error("centroid is not defined in poi.csv, please check it!")
                    sys.exit(0)
                str_centroid = temp_centroid.replace('POINT (', '').replace(')', '').replace(' ', ';').strip().split(';')

                x_coord = str_centroid[0]
                if x_coord:
                    poi.x_coord = float(x_coord)
                else:
                    # print('Error: x_coord is not defined in poi.csv, please check it!')
                    logger.error("x_coord is not defined in poi.csv, please check it!")
                    sys.exit(0)

                y_coord = str_centroid[1]
                if y_coord:
                    poi.y_coord = float(y_coord)
                else:
                    # print('Error: y_coord is not defined in poi.csv, please check it!')
                    logger.error("y_coord is not defined in poi.csv, please check it!")
                    sys.exit(0)


                area = line['area']
                if area:
                    area_meter = float(area)
                else:
                    # print('Error: area is not defined in poi.csv, please check it!')
                    logger.error('area is not defined for POI No.' + str(poi_id) + ' in poi.csv, please check it!')
                    sys.exit(0)

                if area_meter > 90000:  # comments: a simple benchmark to exclude extra large poi nodes
                    poi.area = 0
                    area_feet = 0
                    poi.area_ft2 = 0
                else:
                    poi.area = area_meter
                    area_feet = area_meter * 10.7639104  # comments: convert the area in square meters to square feet
                    poi.area_ft2 = area_feet  # comments: convert the area unit of normal poi nodes to square feet

                building = line['building']
                if building:
                    poi.type = str(building)

                poi.amenity = line['amenity']
                poi.way = line['way']
                poi.geometry = line['geometry']

                g_poi_id_area_dict[poi.id] = area_feet
                g_poi_id_type_dict[poi.id] = poi.type
                g_poi_list.append(poi)
                g_extended_poi_list.append(poi)
                g_poi_map[poi.id] = g_poi_list.index(poi)
                # local_poi_list.append(poi)
    except:
        poi_existing_flag = 1
        logger.info("There is no poi.csv in the folder.")

    logger.debug('Ending ReadNetworkFiles')
    # return local_poi_list,local_node_list

def ReadExternalPOI(input_folder=None):
    logger.debug('Starting ReadExternalPOI')
    global g_external_poi_list
    global g_outside_boundary_node_list
    global g_node_list
    global g_extended_poi_list
    global g_poi_map
    global g_node_id_to_node
    global g_poi_id_to_node_id

    if input_folder:
        external_poi_filepath = os.path.join(input_folder, 'customized_poi.csv')
    else:
        external_poi_filepath = 'customized_poi.csv'

    local_encoding = locale.getdefaultlocale()
    with open(external_poi_filepath, encoding = local_encoding[1]) as fp:
        reader = csv.DictReader(fp)
        node_index = len(g_node_list)
        poi_index = len(g_poi_list)
        exclude_boundary_node_index = len(g_outside_boundary_node_list)
        for line in reader:
            node = Node()
            poi = POI()
            external_poi_name = line['name']
            node.name = external_poi_name
            poi.name = external_poi_name

            external_poi_id = line['poi_id']
            if external_poi_id:
                node.id = int(900000+int(external_poi_id))
                node.poi_id = str(poi_index)
                poi.id = int(poi_index)
                g_node_id_to_index[node.id] = node_index
                g_poi_id_to_node_id[node.poi_id] = node.id
            else:
                logger.error("poi_id is not defined in customized_poi.csv. Please check it!")
                sys.exit(0)

            node.node_type = 'external'
            node.activity_type = 'poi'
            node.activity_location_tab = 'customized'
            node.activity_node_flag = '2'

            area = line['area']
            if area:
                area_meter = float(area)
                poi.area = area_meter
                if area_meter > 90000:  # comments: a simple benchmark to exclude extra large poi nodes
                    poi.area = 0
            else:
                # print('Error: area is not defined in poi.csv, please check it!')
                logger.warning("Field named 'area' is not defined for poi_id " + str(external_poi_id) +
                             ' in customized_poi.csv. Please check it!')
                poi.area = 0

            area_ft2 = line['area_ft2']
            if area_ft2:
                poi.area_ft2 = float(area_ft2)
                if poi.area_ft2 > 968751.936:  # comments: a simple benchmark to exclude extra large poi nodes
                    poi.area_ft2 = 0
            else:
                try:
                    poi.area_ft2 = poi.area * 10.7639104
                except:
                    logger.warning("Field named 'area' and 'area_ft2' are not defined for poi_id " + str(external_poi_id)
                                 + ' in customized_poi.csv. Please check it!')
                    poi.area_ft2 = 0

            try:
                poi.geometry = line['geometry']
            except:
                print("'geometry' field is missed in customized_poi.csv.")
                logger.info("'geometry' field is missed in customized_poi.csv.")
            centroid = ''
            x_coord = ''
            y_coord = ''
            try:
                centroid = line['centroid']
            except:
                logger.info("'centroid' field is missed in customized_poi.csv.")
            try:
                x_coord = line['x_coord']
            except:
                logger.info("'x_coord' field is missed in customized_poi.csv.")
            try:
                y_coord = line['y_coord']
            except:
                logger.info("'y_coord' field is missed in customized_poi.csv.")

            if centroid:
                poi.centroid = str(centroid)
                if x_coord != '' and y_coord != '':
                    node.x_coord = round(float(x_coord),7)
                    node.y_coord = round(float(y_coord),7)
                    poi.x_coord = node.x_coord
                    poi.y_coord = node.y_coord
                else:
                    temp_centroid = str(centroid)
                    str_centroid = temp_centroid.replace('POINT (', '').replace(')', '').replace(' ', ';').strip().split(
                        ';')
                    x_coord = str_centroid[0]
                    if x_coord:
                        node.x_coord = round(float(x_coord),7)
                        poi.x_coord = node.x_coord
                    else:
                        logger.warning("x_coord is not defined. Please check the field named 'centroid'!")
                    y_coord = str_centroid[1]
                    if y_coord:
                        node.y_coord = round(float(y_coord),7)
                        poi.y_coord = node.y_coord
                    else:
                        logger.warning("y_coord is not defined. Please check the field named 'centroid'!")
            else:
                if x_coord and y_coord:
                    node.x_coord = round(float(x_coord),7)
                    node.y_coord = round(float(y_coord),7)
                    poi.x_coord = node.x_coord
                    poi.y_coord = node.y_coord
                    poi.centroid = 'POINT (' + str(node.x_coord) + ' ' + str(node.y_coord) + ')'
                else:
                    logger.error("Centroid information is missed for poi_id " + str(external_poi_id) +
                                   " in customized_poi.csv. Please check it!")
                    sys.exit(0)

            generation_value = line['generation']
            if generation_value:
                node.production = float(generation_value)
            else:
                logger.warning("Trip generation value is not defined for poi_id " + str(external_poi_id) +
                               " in customized_poi.csv. Please check it!")
                node.production = 0
            '''
            production_value = line['production']
            if production_value:
                node.production = float(production_value)
            else:
                logger.warning("Production value is not defined for poi_id " + str(external_poi_id) +
                               " in customized_poi.csv. Please check it!")
                node.production = 0
            attraction_value= line['attraction']
            if attraction_value:
                node.attraction = float(attraction_value)
            else:
                logger.warning("Attraction value is not defined for poi_id " + str(external_poi_id) +
                               " in customized_poi.csv. Please check it!")
                node.attraction = 0
            '''
            g_outside_boundary_node_id_index[node.id] = exclude_boundary_node_index
            g_external_poi_list.append(poi)
            g_outside_boundary_node_list.append(node)
            g_node_list.append(node)
            g_extended_poi_list.append(poi)
            g_poi_map[poi.id] = poi_index
            g_node_id_to_node[node.id] = node

            node_index += 1
            poi_index += 1
            exclude_boundary_node_index += 1

    print("Number of nodes including external poi = ",len(g_node_list))
    logger.debug('Ending ReadExternalPOI')

# def SetDataFormat(lanes):  # to convert the format of link data in colume named 'lanes' to be int
#     data = int(lanes)
#     return data

def SimplifyNet(input_folder=None, link_type_set=None, criteria=None):
    logger.debug('Starting SimplifyNet')
    global g_zone_list
    global g_simplified_poi_list
    global g_useful_linktype_set
    # simplify the transportation network according to link_type_set
    if link_type_set:
        g_useful_linktype_set = link_type_set
    else:
        g_useful_linktype_set = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary'}

    local_encoding = locale.getdefaultlocale()
    if input_folder:
        output_folder = os.path.join(input_folder, 'simplified')
        node_filepath = os.path.join(input_folder, 'node.csv')
        link_filepath = os.path.join(input_folder, 'link.csv')
    else:
        output_folder = 'simplified'
        node_filepath = 'node.csv'
        link_filepath = 'link.csv'
    try:
        nodedata = pd.read_csv(node_filepath)
    except UnicodeDecodeError:
        nodedata = pd.read_csv(node_filepath, encoding=local_encoding[1])
    try:
        linkdata = pd.read_csv(link_filepath)
    except UnicodeDecodeError:
        linkdata = pd.read_csv(link_filepath, encoding=local_encoding[1])

    label_link = linkdata['link_type_name'].isin(g_useful_linktype_set)
    link_major = linkdata[label_link]

    from_node_id_set = set(link_major['from_node_id'])
    to_node_id_set = set(link_major['to_node_id'])
    node_id_set = from_node_id_set.union(to_node_id_set)
    label_node = nodedata['node_id'].isin(node_id_set)
    node_major = nodedata[label_node]
    # link_major['lanes'] = link_major['lanes'].apply(SetDataFormat)
    # print(list(enumerate(link_major['lanes'])))
    # for item in list(enumerate(link_major.loc[:,'lanes'])):
    #     index = np.array(item)[0]
    #     value = np.array(item)[1]
    # print(len(np.array(link_major.loc[:,'lanes'])))
    # link_major.loc[:,'lanes'] = int(link_major.loc[:,'lanes'])
    # print(link_major)
    if not os.path.exists(output_folder): os.mkdir(output_folder)
    node_major.to_csv(os.path.join(output_folder, 'node.csv'), index=False, line_terminator='\n',
                                encoding=local_encoding[1])
    link_major.to_csv(os.path.join(output_folder, 'link.csv'), index=False, line_terminator='\n',
                                encoding=local_encoding[1])

    # simplify POIs by area
    if criteria:
        max_number_of_reserved_poi = criteria
    else:
        max_number_of_reserved_poi = 30  # default value of maximum number of poi nodes in each zone
    count_reserved_poi = 0
    for zone in g_zone_list:
        # if len(zone.poi_node_list) < max_number_of_reserved_poi:
        #     number_of_reserved_poi = len(zone.poi_node_list)
        # else:
        #     number_of_reserved_poi = max_number_of_reserved_poi
        number_of_reserved_poi = min(len(zone.poi_node_list), max_number_of_reserved_poi)
        count_reserved_poi += number_of_reserved_poi
        # print('number_of_reserved_poi in zone ' + str(zone.id) + ' = ' + str(number_of_reserved_poi))
        poi_area_list = [poi.area for poi in zone.poi_node_list]
        poi_index = [i for i in range(0,len(poi_area_list))]
        sorted_area_idx = sorted(enumerate(poi_area_list), key=lambda poi_index:poi_index[1], reverse=True)
        for i in range(0, number_of_reserved_poi):
            index_truple = sorted_area_idx[i]
            # print('The ' + str(i+1) + ' largest area = ' + str(sorted_area_idx[i][1]) + ' (poi_id = ' +
            #       str(zone.poi_node_list[sorted_area_idx[i][0]].id) + ')')
            g_simplified_poi_list.append(zone.poi_node_list[sorted_area_idx[i][0]])
    logger.info('Total number of simplified poi = ' + str(count_reserved_poi))

    # write the simplified poi in the simplified folder
    data = pd.DataFrame([poi.name for poi in g_simplified_poi_list])
    data.columns = ['name']
    data['poi_id'] = pd.DataFrame([poi.id for poi in g_simplified_poi_list])
    data['osm_way_id'] = pd.DataFrame([poi.osm_way_id for poi in g_simplified_poi_list])
    data['osm_relation_id'] = pd.DataFrame([poi.osm_relation_id for poi in g_simplified_poi_list])
    data['building'] = pd.DataFrame([poi.type for poi in g_simplified_poi_list])
    data['amenity'] = pd.DataFrame([poi.amenity for poi in g_simplified_poi_list])
    data['way'] = pd.DataFrame([poi.way for poi in g_simplified_poi_list])
    data['geometry'] = pd.DataFrame([poi.geometry for poi in g_simplified_poi_list])
    data['centroid'] = pd.DataFrame([poi.centroid for poi in g_simplified_poi_list])
    data['area'] = pd.DataFrame([poi.area for poi in g_simplified_poi_list])
    data['area_ft2'] = pd.DataFrame([poi.area_ft2 for poi in g_simplified_poi_list])
    data['activity_zone_id'] = pd.DataFrame([poi.zone_id for poi in g_simplified_poi_list])

    if input_folder:
        output_folder = os.path.join(input_folder, 'simplified')
        poi_filepath = os.path.join(output_folder, 'poi.csv')
        data.to_csv(poi_filepath, index=False, line_terminator='\n', encoding=local_encoding[1])
    else:
        data.to_csv('simplified/poi.csv', index=False, line_terminator='\n', encoding=local_encoding[1])

    logger.debug('Ending SimplifyNet')

def GeneratePOIConnector(input_folder=None):
    global g_used_latitude
    global g_degree_length_dict
    global g_poi_id_to_node_id
    flat_length_km = g_degree_length_dict[g_used_latitude]

    if input_folder:
        working_folder = os.path.join(input_folder, 'simplified')
    else:
        working_folder = 'simplified'
    # find nearest node in the network for each poi
    # obtain local_poi_list, local_node_list by reading the files in simplified folder
    local_node_list = []
    local_poi_list = []
    node_filepath = os.path.join(working_folder, 'node.csv')
    poi_filepath = os.path.join(working_folder, 'poi.csv')
    local_encoding = locale.getdefaultlocale()
    with open(node_filepath, encoding=local_encoding[1]) as fp:
        reader = csv.DictReader(fp)
        for line in reader:
            node = Node()
            node.id = int(line['node_id'])
            x_coord = line['x_coord']
            y_coord = line['y_coord']
            node.x_coord = round(float(x_coord), 7)
            node.y_coord = round(float(y_coord), 7)
            local_node_list.append(node)
    with open(poi_filepath, encoding=local_encoding[1]) as fp:
        reader = csv.DictReader(fp)
        for line in reader:
            poi = POI()
            poi.id = int(line['poi_id'])
            centroid = line['centroid']
            poi.centroid = centroid
            temp_centroid = str(centroid)
            str_centroid = temp_centroid.replace('POINT (', '').replace(')', '').replace(' ', ';').strip().split(';')
            x_coord = str_centroid[0]
            poi.x_coord = float(x_coord)
            y_coord = str_centroid[1]
            poi.y_coord = float(y_coord)
            local_poi_list.append(poi)
    # local_poi_list, local_node_list = ReadNetworkFiles(input_folder=working_folder)
    coord_list = []
    idx_to_node_dict = {}
    for idx in range(len(local_node_list)):
        node = local_node_list[idx]
        coord_list.append((node.x_coord, node.y_coord))
        idx_to_node_dict[idx] = node
    coord_array = np.array(coord_list)
    # print(coord_array)
    # print(local_node_list)
    for poi in local_poi_list:
        # print(poi.id)
        # print(poi.x_coord)
        # print(poi.y_coord)
        poi_coord = np.array((round(poi.x_coord,7), round(poi.y_coord,7)))
        # print(coord_array)
        # print(poi_coord)
        coord_diff = coord_array - poi_coord
        coord_diff_square = np.power(coord_diff,2)
        coord_diff_square_sum = coord_diff_square.sum(axis=1)
        distance = np.sqrt(coord_diff_square_sum)
        idx = np.argmin(distance)
        poi.nearest_node = idx_to_node_dict[idx]
        # print(poi.nearest_node.id)
    # print(len(local_poi_list))

    # generate connector links between poi and its nearest node, and update link.csv
    local_encoding = locale.getdefaultlocale()
    link_filepath = os.path.join(working_folder, 'link.csv')
    try:
        data = pd.read_csv(link_filepath)
    except UnicodeDecodeError:
        data = pd.read_csv(link_filepath, encoding=local_encoding[1])

    link_id_prefix = 100000
    idx = len(data)
    for poi in local_poi_list:
        link1_geometry = 'LINESTRING (' + str(poi.nearest_node.x_coord) + ' ' + str(poi.nearest_node.y_coord) + ' ' + \
                         ',' + str(poi.x_coord) + ' ' + str(poi.y_coord) + ')'
        link2_geometry = 'LINESTRING (' + str(poi.x_coord) + ' ' + str(poi.y_coord) + ' ' + \
                         ',' + str(poi.nearest_node.x_coord) + ' ' + str(poi.nearest_node.y_coord) + ')'
        link1_length = (((float(poi.nearest_node.x_coord) - float(poi.x_coord)) * flat_length_km * 1000) ** 2 +
                           ((float(poi.nearest_node.y_coord) - float(poi.y_coord)) * flat_length_km * 1000) ** 2) ** 0.5
        link2_length = link1_length

        link1_series = pd.Series({"link_id": int(link_id_prefix),
                            "from_node_id": int(poi.nearest_node.id),
                            "to_node_id": int(900000+poi.id),
                            "dir_flag": int(1),
                            "length": link1_length,
                            "lanes": int(2),
                            "free_speed": int(25),
                            "link_type_name": 'connector',
                            "link_type": int(20),
                            "geometry": link1_geometry,
                            "allowed_uses": 'all',
                            "from_biway": int(1)
                            })
        try:
            data.loc[idx] = link1_series
        except:
            data = data.append(link1_series)
        link_id_prefix += 1
        idx += 1

        link2_series = pd.Series({"link_id": int(link_id_prefix),
                                  "from_node_id": int(900000 + poi.id),
                                  "to_node_id": int(poi.nearest_node.id),
                                  "dir_flag": int(1),
                                  "length": link2_length,
                                  "lanes": int(2),
                                  "free_speed": int(25),
                                  "link_type_name": 'connector',
                                  "link_type": int(20),
                                  "geometry": link2_geometry,
                                  "allowed_uses": 'all',
                                  "from_biway": int(1)
                                  })
        try:
            data.loc[idx] = link2_series
        except:
            data = data.append(link2_series)
        link_id_prefix += 1
        idx += 1
    data.to_csv(link_filepath, index=False, line_terminator='\n', encoding=local_encoding[1])

    # append poi nodes to node.csv
    node_filepath = os.path.join(working_folder, 'node.csv')
    try:
        data = pd.read_csv(node_filepath)
    except UnicodeDecodeError:
        data = pd.read_csv(node_filepath, encoding=local_encoding[1])
    idx = len(data)
    for poi in local_poi_list:
        if g_poi_id_to_node_id[str(poi.id)] >= 900000:
            node_series = pd.Series({"node_id": g_poi_id_to_node_id[str(poi.id)],
                                      "activity_type": 'poi',
                                      "x_coord": str(poi.x_coord),
                                      "y_coord": str(poi.y_coord),
                                      "poi_id": int(poi.id),
                                      "activity_location_tab": 'customized'
                                      })
        else:
            node_series = pd.Series({"node_id": g_poi_id_to_node_id[str(poi.id)],
                                     "activity_type": 'poi',
                                     "x_coord": str(poi.x_coord),
                                     "y_coord": str(poi.y_coord),
                                     "poi_id": int(poi.id),
                                     "activity_location_tab": 'poi'
                                     })
        try:
            data.loc[idx] = node_series
        except:
            data = data.append(node_series)
        idx += 1
    data.to_csv(node_filepath, index=False, line_terminator='\n', encoding=local_encoding[1])


"""PART 2  GRID GENERATION"""
g_zone_list = []
g_number_of_zones = 0
g_zone_id_list = []
g_zone_index_dict = {}
g_node_zone_dict = {}
g_poi_zone_dict = {}
g_used_latitude = 0


g_scale_list = [0.006, 0.005, 0.004, 0.003, 0.002, 0.001] # comments: default the scale for each grid zone
g_degree_length_dict = {60: 55.8, 51: 69.47, 45: 78.85, 30: 96.49,
                        0: 111.3}
# comments: default longitudinal length (km) equivalent at selected latitude

alphabet_list = []
for letter in range(65, 91):
    alphabet_list.append(chr(letter))

for letter_1 in range(65, 91):
    for letter_2 in range(65, 91):
        alphabet_list.append(chr(letter_1)+chr(letter_2))

for letter_1 in range(65, 91):
    for letter_2 in range(65, 91):
        for letter_3 in range(65, 91):
            alphabet_list.append(chr(letter_1)+chr(letter_2)+chr(letter_3))

def PartitionGrid(number_of_x_blocks=None,
                  number_of_y_blocks=None,
                  cell_width=None,
                  cell_height=None,
                  latitude=None,
                  external_poi=True,
                  connector=True):
    logger.debug('Starting PartitionGrid')
    # Error: Given grid scales and number of blocks simultaneously
    if ((number_of_x_blocks is not None) and (number_of_y_blocks is not None) \
            and (cell_width is not None) and (cell_height is not None)):
        logger.error('Grid scales and number of blocks can only choose ONE to customize!')
        sys.exit(0)

    global g_number_of_zones
    global g_zone_id_list
    global g_zone_index_dict
    global g_node_zone_dict
    global g_used_latitude
    global g_average_latitude
    global poi_existing_flag

    # initialize parameters
    x_max = max(node.x_coord for node in g_outside_boundary_node_list)
    x_min = min(node.x_coord for node in g_outside_boundary_node_list)
    y_max = max(node.y_coord for node in g_outside_boundary_node_list)
    y_min = min(node.y_coord for node in g_outside_boundary_node_list)

    if latitude is None:  # use the average latitude according to node.csv
        if g_average_latitude == 99:
            latitude = 30  # comments: default value if no given latitude value
            flat_length_per_degree_km = g_degree_length_dict[latitude]
            g_used_latitude = latitude
            logger.warning('Please check y_coord in node.csv! Default latitude is 30 degree!')
        else:
            # match the closest latitude key according to the given latitude
            dif = float('inf')
            for i in g_degree_length_dict.keys():
                if abs(abs(g_average_latitude) - i) < dif:
                    temp_latitude = i
                    dif = abs(abs(g_average_latitude) - i)
                    g_used_latitude = temp_latitude
            flat_length_per_degree_km = g_degree_length_dict[temp_latitude]
    else:  # use the given latitude
        # match the closest latitude key according to the given latitude
        dif = float('inf')
        for i in g_degree_length_dict.keys():
            if abs(abs(latitude) - i) < dif:
                temp_latitude = i
                dif = abs(abs(latitude) - i)
                g_used_latitude = temp_latitude
        flat_length_per_degree_km = g_degree_length_dict[temp_latitude]


    print('\nLatitude used for grid partition = ', g_used_latitude)
    logger.info('Latitude used for grid partition = ' + str(g_used_latitude))

    # Case 0: Default
    if (number_of_x_blocks is None) and (number_of_y_blocks is None) \
            and (cell_width is None) and (cell_height is None):
        logger.warning('Default cell width and height are the length on a flat surface under a specific latitude '
                       'corresponding to the degree of 0.006!')
        scale_x = g_scale_list[0]
        scale_y = g_scale_list[0]
        x_max = math.ceil(x_max / scale_x) * scale_x
        x_min = math.floor(x_min / scale_x) * scale_x
        y_max = math.ceil(y_max / scale_y) * scale_y
        y_min = math.floor(y_min / scale_y) * scale_y
        number_of_x_blocks = round((x_max - x_min) / scale_x)
        number_of_y_blocks = round((y_max - y_min) / scale_y)

    # Case 1: Given number_of_x_blocks and number_of_y_blocks
    if (number_of_x_blocks is not None) and (number_of_y_blocks is not None) \
            and (cell_width is None) and (cell_height is None):
        scale_x = round((x_max - x_min) / number_of_x_blocks, 5) + 0.00001
        scale_y = round((y_max - y_min) / number_of_y_blocks, 5) + 0.00001
        x_max = round(x_min + scale_x * number_of_x_blocks, 5)
        y_min = round(y_max - scale_y * number_of_y_blocks, 5)

    # Case 2: Given scale_x and scale_y in meter
    if (number_of_x_blocks is None) and (number_of_y_blocks is None) \
            and (cell_width is not None) and (cell_height is not None):
        scale_x = round(cell_width / (1000 * flat_length_per_degree_km), 5)
        scale_y = round(cell_height / (1000 * flat_length_per_degree_km), 5)
        x_max = round(math.ceil(x_max / scale_x) * scale_x, 5)
        x_min = round(math.floor(x_min / scale_x) * scale_x, 5)
        y_max = round(math.ceil(y_max / scale_y) * scale_y, 5)
        y_min = round(math.floor(y_min / scale_y) * scale_y, 5)
        number_of_x_blocks = round((x_max - x_min) / scale_x)
        number_of_y_blocks = round((y_max - y_min) / scale_y)

    block_numbers = number_of_x_blocks * number_of_y_blocks
    x_temp = round(x_min, 5)
    y_temp = round(y_max, 5)

    for block_no in range(1, block_numbers + 1):
        block = Zone()
        block.id = block_no
        block.x_min = x_temp
        block.x_max = x_temp + scale_x
        block.y_max = y_temp
        block.y_min = y_temp - scale_y

        for node in g_outside_boundary_node_list:
            if ((node.x_coord <= block.x_max) & (node.x_coord >= block.x_min) \
                    & (node.y_coord <= block.y_max) & (node.y_coord >= block.y_min)) and \
                    (node.activity_type == 'poi' or node.activity_type == 'residential'):
                node.zone_id = str(block.id)
                g_node_zone_dict[node.id] = block.id
                block.node_id_list.append(node.id)

        for poi in g_extended_poi_list:
            if ((poi.x_coord <= block.x_max) & (poi.x_coord >= block.x_min) \
                    & (poi.y_coord <= block.y_max) & (poi.y_coord >= block.y_min)):
                poi.zone_id = str(block.id)
                g_poi_zone_dict[poi.id] = block.id
                block.poi_id_list.append(poi.id)
                block.poi_node_list.append(poi)

        # get centroid coordinates of each zone with nodes by calculating average x_coord and y_coord
        if len(block.node_id_list) != 0:
            block.poi_count = len(block.poi_id_list)  # number of all poi nodes in the zone
            block.residential_count = 0  # number of residential poi nodes in the zone
            block.office_count = 0  # number of office poi nodes in the zone
            block.shopping_count = 0  # number of shopping poi nodes in the zone
            block.school_count = 0  # number of school poi nodes in the zone
            block.parking_count = 0  # number of parking poi nodes in the zone

            for poi in block.poi_node_list:
                if poi.type == 'apartments' or poi.type == 'dormitory' or poi.type == 'house' or poi.type == 'residential':
                    block.residential_count += 1  # number of residential poi nodes in the zone
                elif poi.type == 'office' or poi.type == 'industrial':
                    block.office_count += 1  # number of office poi nodes in the zone
                elif poi.type == 'commercial' or poi.type == 'retail' or poi.type == 'supermarket' or poi.type == 'warehouse':
                    block.shopping_count += 1
                elif poi.type == 'school' or poi.type == 'kindergarten' or poi.type == 'university' \
                    or poi.type == 'college' or poi.type == 'university;yes':
                    block.school_count += 1
                elif poi.type == 'parking' or poi.type == 'garage' or poi.type == 'garages' or poi.type == 'bicycle_parking':
                    block.parking_count += 1  # number of parking poi nodes in the zone

            block.centroid_x = sum(g_outside_boundary_node_list[g_outside_boundary_node_id_index[node_id]].x_coord for
                                   node_id in block.node_id_list) / len(block.node_id_list)
            block.centroid_y = sum(g_outside_boundary_node_list[g_outside_boundary_node_id_index[node_id]].y_coord for
                                   node_id in block.node_id_list) / len(block.node_id_list)
            str_name_a = str(alphabet_list[math.ceil(block.id / number_of_x_blocks) - 1])
            if int(block.id % number_of_x_blocks) != 0:
                str_name_no = str(int(block.id % number_of_x_blocks))
            else:
                str_name_no = str(number_of_x_blocks)
            block.name = str_name_a + str_name_no

            str_polygon = 'POLYGON ((' + \
                          str(block.x_min) + ' ' + str(block.y_min) + ',' + \
                          str(block.x_min) + ' ' + str(block.y_max) + ',' + \
                          str(block.x_max) + ' ' + str(block.y_max) + ',' + \
                          str(block.x_max) + ' ' + str(block.y_min) + ',' + \
                          str(block.x_min) + ' ' + str(block.y_min) + '))'
            block.polygon = str_polygon

            str_centroid = 'POINT (' + str(block.centroid_x) + ' ' + str(block.centroid_y) + ')'
            block.centroid = str_centroid


            centroid_node = Node()
            centroid_node.id = 500000 + block.id
            centroid_node.zone_id = str(block.id)
            centroid_node.x_coord = block.centroid_x
            centroid_node.y_coord = block.centroid_y
            centroid_node.node_type = 'centroid node'
            block.centroid_node = centroid_node
            g_zone_list.append(block)


        # centroid of each zone with zero node is the center point of the grid
        if (len(block.node_id_list) == 0):
            block.poi_count = 0  # number of all poi nodes in the zone
            block.residential_count = 0  # number of residential poi nodes in the zone
            block.office_count = 0  # number of office poi nodes in the zone
            block.shopping_count = 0  # number of shopping poi nodes in the zone
            block.school_count = 0  # number of school poi nodes in the zone
            block.parking_count = 0  # number of parking poi nodes in the zone
            block.centroid_x = (block.x_max + block.x_min) / 2
            block.centroid_y = (block.y_max + block.y_min) / 2
            str_name_a = str(alphabet_list[math.ceil(block.id / number_of_x_blocks) - 1])
            if int(block.id % number_of_x_blocks) != 0:
                str_name_no = str(int(block.id % number_of_x_blocks))
            else:
                str_name_no = str(number_of_x_blocks)
            block.name = str_name_a + str_name_no

            str_polygon = 'POLYGON ((' + \
                          str(block.x_min) + ' ' + str(block.y_min) + ',' + \
                          str(block.x_min) + ' ' + str(block.y_max) + ',' + \
                          str(block.x_max) + ' ' + str(block.y_max) + ',' + \
                          str(block.x_max) + ' ' + str(block.y_min) + ',' + \
                          str(block.x_min) + ' ' + str(block.y_min) + '))'
            block.polygon = str_polygon

            str_centroid = 'POINT (' + str(block.centroid_x) + ' ' + str(block.centroid_y) + ')'
            block.centroid = str_centroid

            centroid_node = Node()
            centroid_node.id = 500000 + block.id
            centroid_node.zone_id = str(block.id)
            centroid_node.x_coord = block.centroid_x
            centroid_node.y_coord = block.centroid_y
            centroid_node.node_type = 'centroid node'
            block.centroid_node = centroid_node
            g_zone_list.append(block)



        if round(abs(x_temp + scale_x - x_max) / scale_x) >= 1:
            x_temp = x_temp + scale_x
        else:
            x_temp = x_min
            y_temp = y_temp - scale_y

    # generate the grid address for boundary nodes and generate virtual zones around the boundary of the area

    # left side virtual zones
    i = 1
    delta_y = 0
    while i <= number_of_y_blocks:
        block = Zone()
        block.id = block_numbers + i
        block.name = 'Gate' + str(i)
        block.x_min = x_min - scale_x / 2
        block.x_max = x_min
        block.y_max = y_min + delta_y + scale_y
        block.y_min = y_min + delta_y
        block.centroid_x = block.x_min
        block.centroid_y = (block.y_max + block.y_min) / 2
        block.centroid = 'POINT (' + str(block.centroid_x) + ' ' + str(block.centroid_y) + ')'
        block.polygon = ''
        block.poi_id_list = []
        block.boundary_count = 0
        for node in g_boundary_node_list:
            if abs(node.x_coord - x_min) == min(abs(node.x_coord - x_max), abs(node.x_coord - x_min),
                                                abs(node.y_coord - y_max), abs(node.y_coord - y_min)) \
                    and block.y_max >= node.y_coord >= block.y_min and node.boundary_flag == 1:
                node.zone_id = str(block.id)
                g_node_zone_dict[node.id] = block.id
                block.node_id_list.append(node.id)
                block.boundary_count += 1

        centroid_node = Node()
        centroid_node.id = 500000 + block.id
        centroid_node.zone_id = str(block.id)
        centroid_node.x_coord = block.centroid_x
        centroid_node.y_coord = block.centroid_y
        centroid_node.node_type = 'centroid node'
        block.centroid_node = centroid_node
        g_zone_list.append(block)

        delta_y += scale_y
        i += 1

    # upper side virtual zones
    i = number_of_y_blocks + 1
    delta_x = 0
    while i <= number_of_y_blocks + number_of_x_blocks:
        block = Zone()
        block.id = block_numbers + i
        block.name = 'Gate' + str(i)
        block.x_min = x_min + delta_x
        block.x_max = x_min + delta_x + scale_x
        block.y_max = y_max + scale_y / 2
        block.y_min = y_max
        block.centroid_x = (block.x_max + block.x_min) / 2
        block.centroid_y = block.y_max
        block.centroid = 'POINT (' + str(block.centroid_x) + ' ' + str(block.centroid_y) + ')'
        block.polygon = ''
        block.poi_id_list = []
        block.boundary_count = 0
        for node in g_boundary_node_list:
            if abs(node.y_coord - y_max) == min(abs(node.x_coord - x_max), abs(node.x_coord - x_min),
                                                abs(node.y_coord - y_max), abs(node.y_coord - y_min)) \
                    and block.x_max >= node.x_coord >= block.x_min and node.boundary_flag == 1:
                node.zone_id = str(block.id)
                g_node_zone_dict[node.id] = block.id
                block.node_id_list.append(node.id)
                block.boundary_count += 1

        centroid_node = Node()
        centroid_node.id = 500000 + block.id
        centroid_node.zone_id = str(block.id)
        centroid_node.x_coord = block.centroid_x
        centroid_node.y_coord = block.centroid_y
        centroid_node.node_type = 'centroid node'
        block.centroid_node = centroid_node
        g_zone_list.append(block)

        i += 1
        delta_x += scale_x

    # right side virtual zones
    i = number_of_y_blocks + number_of_x_blocks + 1
    delta_y = 0
    while i <= 2 * number_of_y_blocks + number_of_x_blocks:
        block = Zone()
        block.id = block_numbers + i
        block.name = 'Gate' + str(i)
        block.x_min = x_max
        block.x_max = x_max + scale_x / 2
        block.y_max = y_max - delta_y
        block.y_min = y_max - delta_y - scale_y
        block.centroid_x = block.x_max
        block.centroid_y = (block.y_max + block.y_min) / 2
        block.centroid = 'POINT (' + str(block.centroid_x) + ' ' + str(block.centroid_y) + ')'
        block.polygon = ''
        block.poi_id_list = []
        block.boundary_count = 0
        for node in g_boundary_node_list:
            if abs(node.x_coord - x_max) == min(abs(node.x_coord - x_max), abs(node.x_coord - x_min),
                                                abs(node.y_coord - y_max), abs(node.y_coord - y_min)) \
                    and block.y_max >= node.y_coord >= block.y_min and node.boundary_flag == 1:
                node.zone_id = str(block.id)
                g_node_zone_dict[node.id] = block.id
                block.node_id_list.append(node.id)
                block.boundary_count += 1

        centroid_node = Node()
        centroid_node.id = 500000 + block.id
        centroid_node.zone_id = str(block.id)
        centroid_node.x_coord = block.centroid_x
        centroid_node.y_coord = block.centroid_y
        centroid_node.node_type = 'centroid node'
        block.centroid_node = centroid_node
        g_zone_list.append(block)

        i += 1
        delta_y += scale_y

    # lower side virtual zones
    i = 2 * number_of_y_blocks + number_of_x_blocks + 1
    delta_x = 0
    while i <= 2 * (number_of_y_blocks + number_of_x_blocks):
        block = Zone()
        block.id = block_numbers + i
        block.name = 'Gate' + str(i)
        block.x_min = x_max - delta_x - scale_x
        block.x_max = x_max - delta_x
        block.y_max = y_min
        block.y_min = y_min - scale_y / 2
        block.centroid_x = (block.x_max + block.x_min) / 2
        block.centroid_y = block.y_min
        block.centroid = 'POINT (' + str(block.centroid_x) + ' ' + str(block.centroid_y) + ')'
        block.polygon = ''
        block.poi_id_list = []
        block.boundary_count = 0
        for node in g_boundary_node_list:
            if abs(node.y_coord - y_min) == min(abs(node.x_coord - x_max), abs(node.x_coord - x_min),
                                                abs(node.y_coord - y_max), abs(node.y_coord - y_min)) \
                    and block.x_max >= node.x_coord >= block.x_min and node.boundary_flag == 1:
                node.zone_id = str(block.id)
                g_node_zone_dict[node.id] = block.id
                block.node_id_list.append(node.id)
                block.boundary_count += 1

        centroid_node = Node()
        centroid_node.id = 500000 + block.id
        centroid_node.zone_id = str(block.id)
        centroid_node.x_coord = block.centroid_x
        centroid_node.y_coord = block.centroid_y
        centroid_node.node_type = 'centroid node'
        block.centroid_node = centroid_node
        g_zone_list.append(block)

        i += 1
        delta_x += scale_x

    g_number_of_zones = len(g_zone_list)
    print('\nNumber of zones including virtual zones = ' + str(g_number_of_zones))
    logger.info('Number of zones including virtual zones = ' + str(g_number_of_zones))
    g_zone_id_list = [zone.id for zone in g_zone_list]

    # get zone index
    for i in range(g_number_of_zones):
        g_zone_index_dict[g_zone_id_list[i]] = i

    """
    # generate the connector
    for block in g_zone_list:
        centroid_node = block.centroid_node

        link_id_temp = 0
        for node_id in block.node_id_list:
            if (link_id_temp < 50):
                if (g_node_list[g_node_id_to_index[node_id]].activity_location_tab in ['residential', 'boundary', 'poi']):

                    connector_link = Link(link_id = block.id * 100000 + link_id_temp,
                                        from_node_id = node_id,
                                        to_node_id = centroid_node.id,
                                        link_type_name = 'connector with ' +
                                                         g_node_list[g_node_id_to_index[node_id]].activity_location_tab,
                                        link_type_id = -1)

                    connector_link.geometry = 'LINESTRING (' + \
                                            str(g_node_list[g_node_id_to_index[node_id]].x_coord) + ' ' + \
                                            str(g_node_list[g_node_id_to_index[node_id]].y_coord) + ' ' + ',' + \
                                            str(centroid_node.x_coord) + ' ' + \
                                            str(centroid_node.y_coord) + ')'

                    block.connector_list.append(connector_link)
                    link_id_temp = link_id_temp + 1
            else:
                break



    with open('connector.csv', 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        line = ['name','link_id','osm_way_id','from_node_id','to_node_id','dir_flag','length','lanes','free_speed',\
            'capacity','link_type_name','link_type','geometry','allowed_uses','from_biway']
        writer.writerow(line)

        for block in g_zone_list:
            for connector_link in block.connector_list:
                line = [ \
                        '', # name
                        connector_link.link_id, # link_id
                        '', # osm_way_id
                        connector_link.from_node_id, # from_node_id
                        connector_link.to_node_id, # to_node_id
                        '', # dir_flag
                        '', # length
                        '', # lanes
                        '', # free_speed
                        '', # capacity
                        connector_link.link_type_name, # link_type_name
                        connector_link.link_type_id, # link_type
                        connector_link.geometry # geometry
                ]
                writer.writerow(line)
    """
    if poi_existing_flag == 0:
        # update poi.csv with zone_id
        local_encoding = locale.getdefaultlocale()
        if g_output_folder is not None:
            poi_filepath = os.path.join(g_output_folder, 'poi.csv')
            try:
                data = pd.read_csv(poi_filepath)
            except UnicodeDecodeError:
                data = pd.read_csv(poi_filepath, encoding=local_encoding[1])
            data_list = [poi.zone_id for poi in g_poi_list]
            data1 = pd.DataFrame(data_list)
            data['activity_zone_id'] = data1
            data_list = [poi.area for poi in g_poi_list]
            data2 = pd.DataFrame(data_list)
            data['area'] = data2
            data_list = [poi.area_ft2 for poi in g_poi_list]
            data3 = pd.DataFrame(data_list)
            data['area_ft2'] = data3
            # print(data)
            data.to_csv(poi_filepath, index=False, line_terminator='\n', encoding=local_encoding[1])

        else:
            try:
                data = pd.read_csv('poi.csv')
            except UnicodeDecodeError:
                data = pd.read_csv('poi.csv', encoding=local_encoding[1])
            data_list = [poi.zone_id for poi in g_poi_list]
            data1 = pd.DataFrame(data_list)
            data['activity_zone_id'] = data1
            data_list = [poi.area for poi in g_poi_list]
            data2 = pd.DataFrame(data_list)
            data['area'] = data2
            data_list = [poi.area_ft2 for poi in g_poi_list]
            data3 = pd.DataFrame(data_list)
            data['area_ft2'] = data3
            # print(data)
            data.to_csv('poi.csv', index=False, line_terminator='\n', encoding=local_encoding[1])

    # update customized_poi.csv with zone_id
    if external_poi == True:
        local_encoding = locale.getdefaultlocale()
        if g_output_folder is not None:
            external_poi_filepath = os.path.join(g_output_folder, 'customized_poi.csv')
            try:
                data = pd.read_csv(external_poi_filepath)
            except UnicodeDecodeError:
                data = pd.read_csv(external_poi_filepath, encoding=local_encoding[1])
            data_list = [poi.zone_id for poi in g_external_poi_list]
            data1 = pd.DataFrame(data_list)
            data['activity_zone_id'] = data1
            data_list = [poi.area for poi in g_external_poi_list]
            data2 = pd.DataFrame(data_list)
            data['area'] = data2
            data_list = [poi.area_ft2 for poi in g_external_poi_list]
            data3 = pd.DataFrame(data_list)
            data['area_ft2'] = data3
            data_list = [poi.x_coord for poi in g_external_poi_list]
            data4 = pd.DataFrame(data_list)
            data['x_coord'] = data4
            data_list = [poi.y_coord for poi in g_external_poi_list]
            data5 = pd.DataFrame(data_list)
            data['y_coord'] = data5
            # print(data)
            data.to_csv(external_poi_filepath, index=False, line_terminator='\n', encoding=local_encoding[1])
        else:
            try:
                data = pd.read_csv('customized_poi.csv')
            except UnicodeDecodeError:
                data = pd.read_csv('customized_poi.csv', encoding=local_encoding[1])
            data_list = [poi.zone_id for poi in g_external_poi_list]
            data1 = pd.DataFrame(data_list)
            data['activity_zone_id'] = data1
            data_list = [poi.area for poi in g_external_poi_list]
            data2 = pd.DataFrame(data_list)
            data['area'] = data2
            data_list = [poi.area_ft2 for poi in g_external_poi_list]
            data3 = pd.DataFrame(data_list)
            data['area_ft2'] = data3
            data_list = [poi.x_coord for poi in g_external_poi_list]
            data4 = pd.DataFrame(data_list)
            data['x_coord'] = data4
            data_list = [poi.y_coord for poi in g_external_poi_list]
            data5 = pd.DataFrame(data_list)
            data['y_coord'] = data5
            # print(data)
            data.to_csv('customized_poi.csv', index=False, line_terminator='\n', encoding=local_encoding[1])


    # create zone.csv
    data_list = [zone.id for zone in g_zone_list]
    data_zone = pd.DataFrame(data_list)
    data_zone.columns = ["activity_zone_id"]

    data_list = [zone.name for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['name'] = data1

    data_list = [zone.centroid_x for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['centroid_x'] = data1

    data_list = [zone.centroid_y for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['centroid_y'] = data1

    data_list = [zone.polygon for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['geometry'] = data1

    data_list = [zone.centroid for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['centroid'] = data1

    data_list = [zone.poi_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['total_poi_count'] = data1

    data_list = [zone.residential_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['residential_poi_count'] = data1

    data_list = [zone.office_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['office_poi_count'] = data1

    data_list = [zone.shopping_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['shopping_poi_count'] = data1

    data_list = [zone.school_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['school_poi_count'] = data1

    data_list = [zone.parking_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['parking_poi_count'] = data1

    data_list = [zone.boundary_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['boundary_node_count'] = data1

    # print(data_zone)
    if g_output_folder is not None:
        zone_filepath = os.path.join(g_output_folder, 'zone.csv')
        data_zone.to_csv(zone_filepath, index=False, line_terminator='\n')
    else:
        data_zone.to_csv('zone.csv', index=False, line_terminator='\n')

    logger.debug("Ending Partition Grid")




"""PART 3  TRIP GENERATION"""
# g_trip_purpose = 0 # comments: this set of global variables are used in the following part 3
g_poi_type_list = []
# g_poi_prod_rate_list = []
# g_poi_attr_rate_list = []
# g_poi_prod_rate_notes_list = []
# g_poi_attr_rate_notes_list = []
g_node_prod_list = []
g_node_attr_list = []
g_node_prod_list0 = []
g_node_attr_list0= []
g_node_prod_list1 = []
g_node_attr_list1 = []
g_node_prod_list2 = []
g_node_attr_list2 = []
g_node_prod_list3 = []
g_node_prod_list4 = []
g_node_prod_list5 = []
g_node_prod_list6 = []
g_node_prod_list7 = []
g_node_prod_list8 = []
# g_undefined_prod_rate_poi_name_list = []
# g_undefined_attr_rate_poi_name_list = []
# g_poi_type_prod_rate_dict = {}
# g_poi_type_attr_rate_dict = {}
# g_poi_prod_rate_flag = {}
# g_poi_attr_rate_flag = {}
g_poi_purpose_prod_dict = defaultdict(defaultdict)
g_poi_purpose_attr_dict = defaultdict(defaultdict)
# trip_purpose_list = [1, 2, 3]
# g_number_of_unmatched_poi_production_rate = 0
# g_number_of_unmatched_poi_attraction_rate = 0
g_zone_to_nodes_dict = {}
g_total_production_list = []
g_total_attraction_list = []
g_poi_generation_rate_dict = {}
g_poi_generation_rate_flag = {}
g_undefined_generation_rate_poi_name_list = []
g_number_of_unmatched_poi_generation_rate = 0
g_poi_generation_rate_list = []
g_poi_generation_rate_notes_list = []
g_purpose_mode_name_list = []
g_time_stamp_name_list = []
g_theta_pm_list = []
g_pm_average_travel_distance_list = []
g_beta_pm_list = []
g_alpha_pm_tau = [[]]*9
g_zone_production = []
g_zone_attraction = []

def GetPoiTripRate(trip_rate_folder=None,
                   trip_purpose=None):
    logger.debug("Starting GetPOITripRate")
    global g_poi_purpose_prod_dict
    global g_poi_purpose_attr_dict
    global g_poi_type_list
    # global g_undefined_prod_rate_poi_name_list
    # global g_undefined_attr_rate_poi_name_list
    # global g_poi_type_prod_rate_dict
    # global g_poi_type_attr_rate_dict
    # global g_trip_purpose
    global g_output_folder
    # global g_number_of_unmatched_poi_production_rate
    # global g_number_of_unmatched_poi_attraction_rate
    global g_poi_generation_rate_dict
    global g_poi_generation_rate_flag
    global g_undefined_generation_rate_poi_name_list
    global g_number_of_unmatched_poi_generation_rate
    global g_poi_generation_rate_list
    global g_number_of_zones
    global g_zone_production
    global g_zone_attraction

    g_zone_production = np.zeros(g_number_of_zones)
    g_zone_attraction = np.zeros(g_number_of_zones)

    if trip_rate_folder:
        trip_rate_filepath = os.path.join(trip_rate_folder, 'poi_trip_rate.csv')
    else:
        trip_rate_filepath = 'poi_trip_rate.csv'

    # define production/attraction rates of each land use type and trip purpose
    try:
        # user can customize poi_trip_rate.csv in advance
        with open(trip_rate_filepath, errors='ignore') as fp:
            reader = csv.DictReader(fp)
            for line in reader:
                poi_type = line['building']
                try:
                    g_poi_generation_rate_dict[poi_type] = float(line['generation_rate'])
                except:
                    g_poi_generation_rate_dict[poi_type] = 0
                '''
                for i in trip_purpose_list:
                    try:
                        g_poi_purpose_prod_dict[poi_type][i] = float(line['production_rate' + str(i)])
                    except:
                        g_poi_purpose_prod_dict[poi_type][i] = 0
                    try:
                        g_poi_purpose_attr_dict[poi_type][i] = float(line['attraction_rate' + str(i)])
                    except:
                        g_poi_purpose_attr_dict[poi_type][i] = 0
                '''

    except:
        # print('Warning: The folder of poi_trip_rate.csv is NOT defined! Default values will be used...')
        logger.warning('poi_trip_rate.csv does not exist in the current folder. Default values will be used.')
        # default trip generation rates refer to ITE Trip Generation Manual, 10t Edition
        # https://www.troutdaleoregon.gov/sites/default/files/fileattachments/public_works/page/966/ite_land_use_list_10th_edition.pdf
        # unit of measure for all poi nodes is 1,000 SF GFA in this version
        '''
        g_poi_purpose_prod_dict = {'parking': {trip_purpose_list[0]: 0.43},
                                   'bicycle_parking': {trip_purpose_list[0]: 0.43},
                                   'digester': {trip_purpose_list[0]: 0.4},
                                   'service': {trip_purpose_list[0]: 0.48}, 'college': {trip_purpose_list[0]: 1.17},
                                   'university': {trip_purpose_list[0]: 1.17}, 'school': {trip_purpose_list[0]: 1.37},
                                   'university;yes': {trip_purpose_list[0]: 1.17},
                                   'kindergarten': {trip_purpose_list[0]: 11.12},
                                   'transportation': {trip_purpose_list[0]: 1.72},
                                   'train_station': {trip_purpose_list[0]: 1.72},
                                   'public': {trip_purpose_list[0]: 0.11},
                                   'public_building': {trip_purpose_list[0]: 0.11},
                                   'hospital': {trip_purpose_list[0]: 0.97},
                                   'government': {trip_purpose_list[0]: 1.71},
                                   'administrative/auxiliary': {trip_purpose_list[0]: 1.71},
                                   'fire_station': {trip_purpose_list[0]: 0.48},
                                   'bakehouse': {trip_purpose_list[0]: 28}, 'temple': {trip_purpose_list[0]: 4.22},
                                   'synagogue': {trip_purpose_list[0]: 0.49}, 'shrine': {trip_purpose_list[0]: 4.22},
                                   'religious': {trip_purpose_list[0]: 0.49}, 'mosque': {trip_purpose_list[0]: 4.22},
                                   'monastery': {trip_purpose_list[0]: 4.22}, 'church': {trip_purpose_list[0]: 0.49},
                                   'chapel': {trip_purpose_list[0]: 0.49}, 'cathedral': {trip_purpose_list[0]: 0.49},
                                   'warehouse': {trip_purpose_list[0]: 0.19}, 'retail': {trip_purpose_list[0]: 6.84},
                                   'supermarket': {trip_purpose_list[0]: 9.24}, 'office': {trip_purpose_list[0]: 1.15},
                                   'kiosk': {trip_purpose_list[0]: 7.42}, 'industrial': {trip_purpose_list[0]: 0.63},
                                   'commercial': {trip_purpose_list[0]: 0.63}, 'library': {trip_purpose_list[0]: 1.17},
                                   'childcare': {trip_purpose_list[0]: 11.12}, 'yes': {trip_purpose_list[0]: 1}}

        g_poi_purpose_attr_dict = {'apartments': {trip_purpose_list[0]: 0.36}, 'bungalow': {trip_purpose_list[0]: 0.99},
                                   'cabin': {trip_purpose_list[0]: 0.99}, 'detached': {trip_purpose_list[0]: 0.99},
                                   'dormitory': {trip_purpose_list[0]: 0.36}, 'ger': {trip_purpose_list[0]: 0.99},
                                   'hotel': {trip_purpose_list[0]: 0.6}, 'house': {trip_purpose_list[0]: 0.44},
                                   'residential': {trip_purpose_list[0]: 0.36},
                                   'semidetached_house': {trip_purpose_list[0]: 0.99},
                                   'static_caravan': {trip_purpose_list[0]: 0.46},
                                   'terrace': {trip_purpose_list[0]: 0.44}, 'public': {trip_purpose_list[0]: 0.11},
                                   'grandstand': {trip_purpose_list[0]: 0.15}, 'pavilion': {trip_purpose_list[0]: 6.29},
                                   'riding_hall': {trip_purpose_list[0]: 3.45},
                                   'sports_hall': {trip_purpose_list[0]: 3.45}, 'stadium': {trip_purpose_list[0]: 0.15},
                                   'yes': {trip_purpose_list[0]: 1}}
        '''
        g_poi_generation_rate_dict = {'office':46,'yes':40,'college':46.8,'dormitory':24.4,'university':46.8,
                                      'apartments':24.4,'bicycle_parking':17.2,'fire_station':9.2,'school':54.8,
                                      'commercial':45.2,'library':46.8,'industrial':25.2,'retail':273.6,
                                      'residential':14.4,'parking':17.2}
    '''
    # Get POI production/attraction rates of each poi type with a specific trip purpose
    if trip_purpose is None:
        # print('Warning: Trip purpose is not defined! Default trip purpose is Purpose 1.')
        logger.warning('Trip purpose is not defined! Default trip purpose is Purpose 1.')
        trip_purpose = trip_purpose_list[0]  # default trip purpose is Purpose 1
        g_trip_purpose = trip_purpose
    else:
        g_trip_purpose = trip_purpose
    '''
    poi_id = [poi.id for poi in g_extended_poi_list]
    poi_type = [poi.type for poi in g_extended_poi_list]
    for i in set(poi_type):
        # define trip generation rate of each poi type
        if i in g_poi_generation_rate_dict.keys():
            g_poi_generation_rate_flag[i] = 1  # comments: the poi type production rate is obtained from the input table
        else:
            g_poi_generation_rate_dict[i] = 10  # comments: define default value of production rate
            g_poi_generation_rate_flag[i] = 0  # comments: the poi type production rate does not exist in the input table
            g_number_of_unmatched_poi_generation_rate += 1
            if i not in g_undefined_generation_rate_poi_name_list:
                # print(g_undefined_trip_rate_poi_name_list)
                g_undefined_generation_rate_poi_name_list.append(i)
                logger.info(
                    'The POI generation rate of ' + "'" + str(i) + "'" +
                    ' is NOT defined! Default generation rate is 10.')
        '''
        # define production rate of each poi type
        if (poi_type[i] in g_poi_purpose_prod_dict):
            production_rate = g_poi_purpose_prod_dict[poi_type[i]][trip_purpose]
            g_poi_type_prod_rate_dict[poi_type[i]] = production_rate
            g_poi_prod_rate_flag[poi_type[i]] = 1  # comments: the poi type production rate is obtained from the input table
        else:
            g_poi_type_prod_rate_dict[poi_type[i]] = 0.1  # comments: define default value of production rate
            g_poi_prod_rate_flag[poi_type[i]] = 0  # comments: the poi type production rate does not exist in the input table
            g_number_of_unmatched_poi_production_rate += 1
            if poi_type[i] not in g_undefined_prod_rate_poi_name_list:
                # print(g_undefined_trip_rate_poi_name_list)
                g_undefined_prod_rate_poi_name_list.append(poi_type[i])
                logger.info(
                    'The POI production rate of ' + "'" + str(poi_type[i]) + "'" +
                    ' is NOT defined! Default production rate is 0.1.')

        # define attraction rate of each poi type
        if (poi_type[i] in g_poi_purpose_attr_dict):
            attraction_rate = g_poi_purpose_attr_dict[poi_type[i]][trip_purpose]
            g_poi_type_attr_rate_dict[poi_type[i]] = attraction_rate
            g_poi_attr_rate_flag[poi_type[i]] = 1  # comments: the poi type attraction rate is obtained from the input table
        else:
            g_poi_type_attr_rate_dict[poi_type[i]] = 0.1  # comments: define default value of attraction rate
            g_poi_attr_rate_flag[poi_type[i]] = 0  # comments: the poi type attraction rate does not exist in the input table
            g_number_of_unmatched_poi_attraction_rate += 1
            if poi_type[i] not in g_undefined_attr_rate_poi_name_list:
                g_undefined_attr_rate_poi_name_list.append(poi_type[i])
                logger.info(
                    'The POI attraction rate of ' + "'" + str(poi_type[i]) + "'" +
                    ' is NOT defined! Default production rate is 0.1.')
        '''

    # print('\nTab of trip purposes used in grid2demand = ', g_trip_purpose)
    print('\nTotal number of poi nodes with unmatched generation rate = ', g_number_of_unmatched_poi_generation_rate)
    logger.info('Total number of poi nodes with unmatched generation rates = ' + str(
        g_number_of_unmatched_poi_generation_rate))
    # print('\nTotal number of poi nodes with unmatched production rate = ', g_number_of_unmatched_poi_production_rate)
    # print('Total number of poi nodes with unmatched attraction rate = ', g_number_of_unmatched_poi_attraction_rate)
    # logger.info('Tab of trip purpose used in grid2demand = ' + str(g_trip_purpose))
    # logger.info('Total number of poi nodes with unmatched production rates = ' + str(
    #     g_number_of_unmatched_poi_production_rate))
    # logger.info('Total number of poi nodes with unmatched attraction rates = ' + str(
    #     g_number_of_unmatched_poi_attraction_rate))

    # create poi_trip_rate.csv
    poi_type = [poi.type for poi in g_extended_poi_list]
    g_poi_type_list = list(set(poi_type))  # comments: obtain unique poi types

    data_index = [i for i in range(len(g_poi_type_list))]
    data_rate = pd.DataFrame(data_index)
    data_rate.columns = ["poi_type_id"]

    data_type = [building for building in g_poi_type_list]
    data_rate['building'] = pd.DataFrame(data_type)

    data_rate['unit_of_measure'] = pd.DataFrame(['1,000 Sq. Ft. GFA'] * len(g_poi_type_list))

    # data_rate['trip_purpose'] = pd.DataFrame([g_trip_purpose] * len(g_poi_type_list))

    for item in g_poi_type_list:
        g_poi_generation_rate_list.append(g_poi_generation_rate_dict[str(item)])
        g_poi_generation_rate_notes_list.append(g_poi_generation_rate_flag[str(item)])
        # g_poi_prod_rate_list.append(g_poi_type_prod_rate_dict[item])
        # g_poi_attr_rate_list.append(g_poi_type_attr_rate_dict[item])
        # g_poi_prod_rate_notes_list.append(g_poi_prod_rate_flag[item])
        # g_poi_attr_rate_notes_list.append(g_poi_attr_rate_flag[item])

    data_rate['generation_rate'] = pd.DataFrame(g_poi_generation_rate_list)
    data_rate['notes'] = pd.DataFrame(g_poi_generation_rate_notes_list)
    # data_rate['production_rate' + str(g_trip_purpose)] = pd.DataFrame(g_poi_prod_rate_list)
    # data_rate['attraction_rate' + str(g_trip_purpose)] = pd.DataFrame(g_poi_attr_rate_list)
    # data_rate['production_notes'] = pd.DataFrame(g_poi_prod_rate_notes_list)
    # data_rate['attraction_notes'] = pd.DataFrame(g_poi_attr_rate_notes_list)

    # print(data_rate)
    if g_output_folder is not None:
        triprate_filepath = os.path.join(g_output_folder, 'poi_trip_rate.csv')
        data_rate.to_csv(triprate_filepath, index=False, line_terminator='\n')
    else:
        data_rate.to_csv('poi_trip_rate.csv', index=False, line_terminator='\n')

    logger.debug('Ending GetPOITripRate')


def GetNodeDemand(residential_generation=None, boundary_generation=None):
    logger.debug('Starting GetNodeDemand')
    global g_node_prod_list
    global g_node_attr_list
    global g_node_prod_list0
    global g_node_attr_list0
    global g_node_prod_list1
    global g_node_attr_list1
    global g_node_prod_list2
    global g_node_attr_list2
    global g_node_prod_list3
    global g_node_prod_list4
    global g_node_prod_list5
    global g_node_prod_list6
    global g_node_prod_list7
    global g_node_prod_list8
    global g_node_list
    global g_output_folder
    global g_zone_to_nodes_dict
    global g_total_production_list
    global g_total_attraction_list
    global g_purpose_mode_name_list
    global g_time_stamp_name_list
    global g_theta_pm_list
    global g_pm_average_travel_distance_list
    global g_beta_pm_list
    global g_alpha_pm_tau
    global g_zone_production
    global g_zone_attraction

    activity_rate_filepath = os.path.join(g_output_folder, 'purpose_mode_rate.csv')
    activity_rate = pd.read_csv(activity_rate_filepath)
    g_purpose_mode_name_list = activity_rate['purpose_mode_name']
    g_time_stamp_name_list = activity_rate.iloc[1,4:100].index.tolist()
    try:
        proportion = activity_rate['proportion']
    except:
        proportion = [0.05, 0.15, 0.1, 0.05, 0.15, 0.1, 0.2, 0.1, 0.1]  # default values of purpose-mode split
        logger.warning('Purpose-mode split is not defined in purpose_mode_rate.csv! '
                       'Default values are [0.05, 0.15, 0.1, 0.05, 0.15, 0.1, 0.2, 0.1, 0.1].')
    g_theta_pm_list = proportion

    try:
        g_pm_average_travel_distance_list = activity_rate['average_travel_miles']
    except:
        g_pm_average_travel_distance_list = [13, 8, 15, 13, 8, 15, 12, 4, 2]  # default values of average travel distance
        logger.warning('Average travel distance is not defined in purpose_mode_rate.csv! '
                       'Default values are [13, 8, 15, 13, 8, 15, 12, 4, 2].')
    g_beta_pm_list = [1/i for i in g_pm_average_travel_distance_list]

    for i in range(9):  # totally 9 purpose-mode types
        g_alpha_pm_tau[i] = activity_rate.iloc[i, 4:100]
    '''
    if residential_production is None:
        logger.warning('Production value of residential nodes is not defined! Default value is 10.')
        residential_production = 10  # comments: default value if no given residential_production
    if residential_attraction is None:
        logger.warning('Attraction value of residential nodes is not defined! Default value is 10.')
        residential_attraction = 10  # comments: default value if no given residential_attraction
    if boundary_production is None:
        logger.warning('Production value of boundary nodes is not defined! Default value is 1000.')
        boundary_production = 1000  # comments: default value if no given boundary_production
    if boundary_attraction is None:
        logger.warning('Attraction value of boundary nodes is not defined! Default value is 1000.')
        boundary_attraction = 1000  # comments: default value if no given boundary_attraction
    '''
    if residential_generation is None:
        logger.warning('Generation value of residential nodes is not defined! Default value is 500.')
        residential_attraction = 500  # comments: default value if no given residential_attraction
    if boundary_generation is None:
        logger.warning('Generation value of boundary nodes is not defined! Default value is 10000.')
        boundary_generation = 10000  # comments: default value if no given boundary_production

    # calculate production/attraction values of each node
    log_flag = 0
    for node in g_node_list:
        if node.activity_location_tab == 'residential':  # residential node
            g_node_prod_list.append(residential_generation)  # comments: default production value of residential node
            g_node_prod_list0.append(residential_generation * proportion[0])
            g_node_prod_list1.append(residential_generation * proportion[1])
            g_node_prod_list2.append(residential_generation * proportion[2])
            g_node_prod_list3.append(residential_generation * proportion[3])
            g_node_prod_list4.append(residential_generation * proportion[4])
            g_node_prod_list5.append(residential_generation * proportion[5])
            g_node_prod_list6.append(residential_generation * proportion[6])
            g_node_prod_list7.append(residential_generation * proportion[7])
            g_node_prod_list8.append(residential_generation * proportion[8])
            node.production = residential_generation
            # g_node_attr_list.append(residential_attraction)  # comments: default attraction value of residential node
            # g_node_attr_list0.append(residential_attraction * rate[3])
            # g_node_attr_list1.append(residential_attraction * rate[4])
            # g_node_attr_list2.append(residential_attraction * rate[5])
            # node.attraction = residential_attraction

        elif node.activity_location_tab == 'boundary' and node.activity_type in g_useful_linktype_set:
            # boundary nodes only in simplified network
            g_node_prod_list.append(boundary_generation)  # comments: default production value of boundary node
            g_node_prod_list0.append(boundary_generation * proportion[0])
            g_node_prod_list1.append(boundary_generation * proportion[1])
            g_node_prod_list2.append(boundary_generation * proportion[2])
            g_node_prod_list3.append(boundary_generation * proportion[3])
            g_node_prod_list4.append(boundary_generation * proportion[4])
            g_node_prod_list5.append(boundary_generation * proportion[5])
            g_node_prod_list6.append(boundary_generation * proportion[6])
            g_node_prod_list7.append(boundary_generation * proportion[7])
            g_node_prod_list8.append(boundary_generation * proportion[8])
            node.production = boundary_generation
            # g_node_attr_list.append(boundary_attraction)  # comments: default attraction value of boundary node
            # g_node_attr_list0.append(boundary_attraction * rate[3])
            # g_node_attr_list1.append(boundary_attraction * rate[4])
            # g_node_attr_list2.append(boundary_attraction * rate[5])
            # node.attraction = boundary_attraction

        elif node.activity_location_tab == 'poi':  # poi node
            # define production value of each poi node
            if (int(float(node.poi_id)) in g_poi_id_type_dict.keys()):
                node_poi_type = g_poi_id_type_dict[int(float(node.poi_id))]
                node_poi_prod = g_poi_generation_rate_dict[node_poi_type] * g_poi_id_area_dict[
                    int(float(node.poi_id))] / 1000  # convert the unit of measure to be 1,000 Sq. Ft. GFA
                node.production = node_poi_prod
                g_node_prod_list.append(node_poi_prod)
                g_node_prod_list0.append(node_poi_prod * proportion[0])
                g_node_prod_list1.append(node_poi_prod * proportion[1])
                g_node_prod_list2.append(node_poi_prod * proportion[2])
                g_node_prod_list3.append(node_poi_prod * proportion[3])
                g_node_prod_list4.append(node_poi_prod * proportion[4])
                g_node_prod_list5.append(node_poi_prod * proportion[5])
                g_node_prod_list6.append(node_poi_prod * proportion[6])
                g_node_prod_list7.append(node_poi_prod * proportion[7])
                g_node_prod_list8.append(node_poi_prod * proportion[8])
            '''
            # define attraction value of each poi node
            if (int(float(node.poi_id)) in g_poi_id_type_dict.keys()):
                node_poi_type = g_poi_id_type_dict[int(float(node.poi_id))]
                node_poi_attr = g_poi_type_attr_rate_dict[node_poi_type] * g_poi_id_area_dict[
                    int(float(node.poi_id))] / 1000  # convert the unit of measure to be 1,000 Sq. Ft. GFA
                node.attraction = node_poi_attr
                g_node_attr_list.append(node_poi_attr)
                # g_node_attr_list0.append(node_poi_attr * rate[3])
                # g_node_attr_list1.append(node_poi_attr * rate[4])
                # g_node_attr_list2.append(node_poi_attr * rate[5])
            '''

        elif node.activity_location_tab == 'customized':  # external poi node
            g_node_prod_list.append(node.production)  # comments: given production value of external poi node
            g_node_prod_list0.append(node.production * proportion[0])
            g_node_prod_list1.append(node.production * proportion[1])
            g_node_prod_list2.append(node.production * proportion[2])
            g_node_prod_list3.append(node.production * proportion[3])
            g_node_prod_list4.append(node.production * proportion[4])
            g_node_prod_list5.append(node.production * proportion[5])
            g_node_prod_list6.append(node.production * proportion[6])
            g_node_prod_list7.append(node.production * proportion[7])
            g_node_prod_list8.append(node.production * proportion[8])
            # g_node_attr_list.append(node.attraction)  # comments: given attraction value of external poi node
            # g_node_attr_list0.append(node.attraction * rate[3])
            # g_node_attr_list1.append(node.attraction * rate[4])
            # g_node_attr_list2.append(node.attraction * rate[5])

        else:
            g_node_prod_list.append(0)
            g_node_prod_list0.append(0)
            g_node_prod_list1.append(0)
            g_node_prod_list2.append(0)
            g_node_prod_list3.append(0)
            g_node_prod_list4.append(0)
            g_node_prod_list5.append(0)
            g_node_prod_list6.append(0)
            g_node_prod_list7.append(0)
            g_node_prod_list8.append(0)
            node.production = 0

            # g_node_attr_list.append(0)
            # g_node_attr_list0.append(0)
            # g_node_attr_list1.append(0)
            # g_node_attr_list2.append(0)
            # node.attraction = 0
            if (log_flag == 0):
                logger.info("This is not a node producing or attracting demand. Default value of generation is 0.")
                log_flag = 1

    # update node.csv with zone_id and demand values
    data = pd.DataFrame([node.name for node in g_node_list])
    data.columns = ['name']
    data['node_id'] = pd.DataFrame([node.id for node in g_node_list])
    data['osm_node_id'] = pd.DataFrame([node.osm_node_id for node in g_node_list])
    data['osm_highway'] = pd.DataFrame([node.osm_highway for node in g_node_list])
    data['zone_id'] = pd.DataFrame([node.zone_id for node in g_node_list])
    data['ctrl_type'] = pd.DataFrame([node.ctrl_type for node in g_node_list])
    data['node_type'] = pd.DataFrame([node.node_type for node in g_node_list])
    data['activity_type'] = pd.DataFrame([node.activity_type for node in g_node_list])
    data['is_boundary'] = pd.DataFrame([node.boundary_flag for node in g_node_list])
    data['x_coord'] = pd.DataFrame([node.x_coord for node in g_node_list])
    data['y_coord'] = pd.DataFrame([node.y_coord for node in g_node_list])
    data['main_node_id'] = pd.DataFrame([node.main_node_id for node in g_node_list])
    data['poi_id'] = pd.DataFrame([node.poi_id for node in g_node_list])
    data['notes'] = pd.DataFrame([node.notes for node in g_node_list])
    data['activity_zone_id'] = pd.DataFrame([node.zone_id for node in g_node_list])
    data['activity_location_tab'] = pd.DataFrame([node.activity_location_tab for node in g_node_list])
    data['activity_node_flag'] = pd.DataFrame([node.activity_node_flag for node in g_node_list])
    data['total_trip_generation'] = pd.DataFrame(g_node_prod_list)
    # data['total_attraction'] = pd.DataFrame(g_node_attr_list)
    data['generation_0'] = pd.DataFrame(g_node_prod_list0)
    data['generation_1'] = pd.DataFrame(g_node_prod_list1)
    data['generation_2'] = pd.DataFrame(g_node_prod_list2)
    data['generation_3'] = pd.DataFrame(g_node_prod_list3)
    data['generation_4'] = pd.DataFrame(g_node_prod_list4)
    data['generation_5'] = pd.DataFrame(g_node_prod_list5)
    data['generation_6'] = pd.DataFrame(g_node_prod_list6)
    data['generation_7'] = pd.DataFrame(g_node_prod_list7)
    data['generation_8'] = pd.DataFrame(g_node_prod_list8)

    local_encoding = locale.getdefaultlocale()
    if g_output_folder is not None:
        node_filepath = os.path.join(g_output_folder, 'node.csv')
        data.to_csv(node_filepath, index=False, line_terminator='\n', encoding=local_encoding[1])
    else:
        data.to_csv('node.csv', index=False, line_terminator='\n', encoding=local_encoding[1])


    # calculate zone production / attraction, and update zone.csv
    for node in g_node_list:
        g_node_production_dict[node.id] = float(node.production)
        g_node_attraction_dict[node.id] = float(node.attraction)
        g_node_id_list.append(node.id)
        g_node_zone_id_list.append(node.zone_id)
        # judge whether the node is the simplified poi or boundary
        if node.boundary_flag == 1 and node.activity_type in g_useful_linktype_set:
            # only one boundary node of each virtual zone is used to generate agents
            if node.zone_id != '' and node.zone_id not in g_zone_to_nodes_dict.keys():
                g_zone_to_nodes_dict[node.zone_id] = list()
                g_zone_to_nodes_dict[node.zone_id].append(node.id)
        elif node.activity_type == 'poi':  # only poi nodes in g_simplified_poi_list can be used to generate agents
            simplified_poi_id_list = [int(poi.id) for poi in g_simplified_poi_list]
            if int(node.poi_id) in simplified_poi_id_list:
                # print('node.poi_id: ', node.poi_id)
                # print('simplified_poi_id_list: ', simplified_poi_id_list)
                if node.zone_id != '' and node.zone_id not in g_zone_to_nodes_dict.keys():
                    g_zone_to_nodes_dict[node.zone_id] = list()
                    g_zone_to_nodes_dict[node.zone_id].append(node.id)
                elif node.zone_id != '':
                    g_zone_to_nodes_dict[node.zone_id].append(node.id)

    g_number_of_nodes = len(g_node_list)

    "deal with multiple nodes within one zone"
    error_flag = 0
    for i in range(g_number_of_nodes):
        if g_node_list[i].activity_location_tab == 'poi' or g_node_list[i].activity_location_tab == 'boundary' or \
                g_node_list[i].activity_location_tab == 'residential' or \
                g_node_list[i].activity_location_tab == 'customized':
            node_id = g_node_id_list[i]
            if g_node_zone_dict.get(node_id) is not None:
                zone_id = g_node_zone_dict[node_id]
                zone_index = g_zone_index_dict[zone_id]
                node_prod = g_node_production_dict[node_id]
                node_attr = g_node_attraction_dict[node_id]
                g_zone_production[zone_index] = g_zone_production[zone_index] + node_prod
                g_zone_attraction[zone_index] = g_zone_attraction[zone_index] + node_attr
                error_flag += 1
    if error_flag == 0:
        logger.error("There is no node with activity_type = 'poi/residential' or is_boundary = '1'. Please check "
                     "node.csv!")
        sys.exit(0)

    for zone in g_zone_list:
        zone_index = g_zone_index_dict[zone.id]
        g_total_production_list.append(g_zone_production[zone_index])
        g_total_attraction_list.append(g_zone_attraction[zone_index])

    # update zone.csv with total production and attraction in each zone
    data_list = [zone.id for zone in g_zone_list]
    data_zone = pd.DataFrame(data_list)
    data_zone.columns = ["activity_zone_id"]

    data_zone_name_list = [zone.name for zone in g_zone_list]
    data1 = pd.DataFrame(data_zone_name_list)
    data_zone['name'] = data1

    data_list = [zone.centroid_x for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['centroid_x'] = data1

    data_list = [zone.centroid_y for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['centroid_y'] = data1

    data_list = [zone.polygon for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['geometry'] = data1

    data_list = [zone.centroid for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['centroid'] = data1

    data_list = [zone.poi_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['total_poi_count'] = data1

    data_list = [zone.residential_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['residential_poi_count'] = data1

    data_list = [zone.office_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['office_poi_count'] = data1

    data_list = [zone.shopping_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['shopping_poi_count'] = data1

    data_list = [zone.school_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['school_poi_count'] = data1

    data_list = [zone.parking_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['parking_poi_count'] = data1

    data_list = [zone.boundary_count for zone in g_zone_list]
    data1 = pd.DataFrame(data_list)
    data_zone['boundary_node_count'] = data1



    data_zone['total_trip_generation'] = pd.DataFrame(g_total_production_list)
    # data_zone['total_attraction'] = pd.DataFrame(g_total_attraction_list)

    max_prod_o_zone_index = g_total_production_list.index(max(g_total_production_list))
    max_attr_d_zone_index = g_total_attraction_list.index(max(g_total_attraction_list))
    print('\nZone with the largest trip generation volume is ' + str(data_zone_name_list[max_prod_o_zone_index]))
    logger.info('Zone with the largest generation volume is ' + str(data_zone_name_list[max_prod_o_zone_index]))
    # print('Origin zone with largest production volume is '+str(data_zone_name_list[max_prod_o_zone_index]))
    # print('Destination zone with largest attraction volume is ' + str(data_zone_name_list[max_attr_d_zone_index]))
    # logger.info('Origin zone with largest production volume is '+str(data_zone_name_list[max_prod_o_zone_index]))
    # logger.info('Destination zone with largest attraction volume is ' + str(data_zone_name_list[max_attr_d_zone_index]))

    # print(data_zone)

    if g_output_folder is not None:
        zone_filepath = os.path.join(g_output_folder, 'zone.csv')
        data_zone.to_csv(zone_filepath, index=False, line_terminator='\n')
    else:
        data_zone.to_csv('zone.csv', index=False, line_terminator='\n')

    logger.debug('Ending GetNodeDemand')


"""PART 4  CALCULATE ACCESSIBILITY"""
o_zone_id_list = []
o_zone_name_list = []
d_zone_id_list = []
d_zone_name_list = []
od_distance_list = []
od_geometry_list = []
g_distance_matrix = []

def ProduceAccessMatrix(latitude=None, accessibility_folder=None):
    logger.debug('Starting ProduceAccessMatrix')
    global o_zone_id_list
    global o_zone_name_list
    global d_zone_id_list
    global d_zone_name_list
    global od_distance_list
    global od_geometry_list
    global g_distance_matrix
    global g_output_folder
    global g_used_latitude
    global g_average_latitude

    g_distance_matrix = np.ones((g_number_of_zones, g_number_of_zones)) * 9999  # initialize distance matrix

    if latitude is None:  # use the average latitude according to node.csv
        if g_average_latitude == 99:
            logger.warning('Please check y_coord in node.csv! Default latitude is 30 degree!')
            latitude = 30  # comments: default value if no given latitude
            flat_length = g_degree_length_dict[latitude]
            g_used_latitude = latitude
        else:
            # match the closest latitude key according to the given latitude
            dif = float('inf')
            for i in g_degree_length_dict.keys():
                if abs(abs(g_average_latitude) - i) < dif:
                    temp_latitude = i
                    dif = abs(abs(g_average_latitude) - i)
                    g_used_latitude = temp_latitude
            flat_length = g_degree_length_dict[temp_latitude]
    else:  # use the given latitude
        # match the closest latitude key according to the given latitude
        dif = float('inf')
        for i in g_degree_length_dict.keys():
            if abs(abs(latitude) - i) < dif:
                temp_latitude = i
                dif = abs(abs(latitude) - i)
                g_used_latitude = temp_latitude
        flat_length = g_degree_length_dict[temp_latitude]

    print('\nLatitude used for calculating accessibility = ', g_used_latitude)
    logger.info('Latitude used for calculating accessibility = ' + str(g_used_latitude))

    # define accessibility by calculating straight distance between zone centroids
    if accessibility_folder:
        accessibility_filepath = os.path.join(accessibility_folder, 'accessibility.csv')
    else:
        accessibility_filepath = 'accessibility.csv'

    for o_zone in g_zone_list:
        for d_zone in g_zone_list:
            o_zone_id_list.append(o_zone.id)
            o_zone_name_list.append(o_zone.name)
            d_zone_id_list.append(d_zone.id)
            d_zone_name_list.append(d_zone.name)
            od_geometry_list.append(
                'LINESTRING (' + str(round(o_zone.centroid_x, 7)) + ' ' + str(round(o_zone.centroid_y, 7))
                + ',' + str(round(d_zone.centroid_x, 7)) + ' ' + str(round(d_zone.centroid_y, 7)) + ')')
            distance_km = (((float(o_zone.centroid_x) - float(d_zone.centroid_x)) * flat_length) ** 2 +
                           ((float(o_zone.centroid_y) - float(d_zone.centroid_y)) * flat_length) ** 2) ** 0.5
            od_distance_list.append(distance_km)
            o_zone_index = g_zone_index_dict[o_zone.id]
            d_zone_index = g_zone_index_dict[d_zone.id]
            g_distance_matrix[o_zone_index][d_zone_index] = distance_km

    # create accessibility.csv
    data = pd.DataFrame(o_zone_id_list)
    print('\nNumber of OD pairs = ', len(o_zone_id_list))
    logger.info('Number of OD pairs = '+str(len(o_zone_id_list)))
    data.columns = ["o_zone_id"]
    data["o_zone_name"] = pd.DataFrame(o_zone_name_list)

    data1 = pd.DataFrame(d_zone_id_list)
    data['d_zone_id'] = data1
    data["d_zone_name"] = pd.DataFrame(d_zone_name_list)

    data2 = pd.DataFrame(od_distance_list)
    data['accessibility'] = data2
    max_accessibility_index = od_distance_list.index(max(od_distance_list))
    sum = 0
    for i in od_distance_list:
        sum += float(i)
    print('\nLargest accessibility of distance = '+str(round(od_distance_list[max_accessibility_index],2))+' km')
    print('Average accessibility of distance = '+str(round(sum/len(od_distance_list),2))+' km')
    logger.info('Largest accessibility of distance = '+str(round(od_distance_list[max_accessibility_index],2))+' km')
    logger.info('Average accessibility of distance = '+str(round(sum/len(od_distance_list),2))+' km')

    data3 = pd.DataFrame(od_geometry_list)
    data['geometry'] = data3

    # print(data)
    if g_output_folder is not None:
        accessibility_filepath = os.path.join(g_output_folder, 'accessibility.csv')
        data.to_csv(accessibility_filepath, index=False, line_terminator='\n')
    else:
        data.to_csv('accessibility.csv', index=False, line_terminator='\n')
    logger.debug("Ending ProduceAccessMatrix")


"""PART 5  TRIP DISTRIBUTION"""
g_node_id_list = []
g_node_zone_id_list = []
g_node_production_dict = {}
g_node_attraction_dict = {}
g_trip_matrix = []
g_scaling_factor = 1

def RunGravityModel(a=None, b=None, c=None):
    logger.debug("Starting RunGravityModel")
    global g_node_id_list
    global g_node_production_dict
    global g_node_attraction_dict
    global g_trip_matrix
    global g_output_folder
    global g_useful_linktype_set
    global g_zone_production
    global g_zone_attraction

    # for node in g_node_list:
    #     mm=node.production
    #     g_node_production_dict[node.id] = float(node.production)
    #     g_node_attraction_dict[node.id] = float(node.attraction)
    #     g_node_id_list.append(node.id)
    #     g_node_zone_id_list.append(node.zone_id)
    #     # judge whether the node is the simplified poi or boundary
    #     if node.boundary_flag == 1 and node.activity_type in g_useful_linktype_set:
    #         # only one boundary node of each virtual zone is used to generate agents
    #         if node.zone_id != '' and node.zone_id not in g_zone_to_nodes_dict.keys():
    #             g_zone_to_nodes_dict[node.zone_id] = list()
    #             g_zone_to_nodes_dict[node.zone_id].append(node.id)
    #     elif node.activity_type == 'poi':  # only poi nodes in g_simplified_poi_list can be used to generate agents
    #         simplified_poi_id_list = [int(poi.id) for poi in g_simplified_poi_list]
    #         if int(node.poi_id) in simplified_poi_id_list:
    #             # print('node.poi_id: ', node.poi_id)
    #             # print('simplified_poi_id_list: ', simplified_poi_id_list)
    #             if node.zone_id != '' and node.zone_id not in g_zone_to_nodes_dict.keys():
    #                 g_zone_to_nodes_dict[node.zone_id] = list()
    #                 g_zone_to_nodes_dict[node.zone_id].append(node.id)
    #             elif node.zone_id != '':
    #                 g_zone_to_nodes_dict[node.zone_id].append(node.id)
    #
    # g_number_of_nodes = len(g_node_list)
    #
    # "deal with multiple nodes within one zone"
    # g_zone_production = np.zeros(g_number_of_zones)
    # g_zone_attraction = np.zeros(g_number_of_zones)
    # error_flag = 0
    # for i in range(g_number_of_nodes):
    #     if g_node_list[i].activity_location_tab == 'poi' or g_node_list[i].activity_location_tab == 'boundary' or \
    #             g_node_list[i].activity_location_tab == 'residential' or \
    #             g_node_list[i].activity_location_tab == 'customized':
    #         node_id = g_node_id_list[i]
    #         if g_node_zone_dict.get(node_id) is not None:
    #             zone_id = g_node_zone_dict[node_id]
    #             zone_index = g_zone_index_dict[zone_id]
    #             node_prod = g_node_production_dict[node_id]
    #             node_attr = g_node_attraction_dict[node_id]
    #             g_zone_production[zone_index] = g_zone_production[zone_index] + node_prod
    #             g_zone_attraction[zone_index] = g_zone_attraction[zone_index] + node_attr
    #             error_flag += 1
    # if error_flag == 0:
    #     logger.error("There is no node with activity_type = 'poi/residential' or is_boundary = '1'. Please check "
    #                  "node.csv!")
    #     sys.exit(0)
    #
    # for zone in g_zone_list:
    #     zone_index = g_zone_index_dict[zone.id]
    #     g_total_production_list.append(g_zone_production[zone_index])
    #     g_total_attraction_list.append(g_zone_attraction[zone_index])

    "perform the distribution with friction matrix"
    g_friction_matrix = np.ones((g_number_of_zones, g_number_of_zones)) * 9999  # initialize friction matrix
    for o_zone in g_zone_list:
        for d_zone in g_zone_list:
            o_zone_index = g_zone_index_dict[o_zone.id]
            d_zone_index = g_zone_index_dict[d_zone.id]
            od_distance = g_distance_matrix[o_zone_index][d_zone_index]
            if od_distance != 0:
                g_friction_matrix[o_zone_index][d_zone_index] = 1/od_distance
            else:
                g_friction_matrix[o_zone_index][d_zone_index] = 0

    "step 1: calculate total attraction for each zone"
    g_trip_matrix = np.zeros((g_number_of_zones, g_number_of_zones))
    total_attraction_friction = np.zeros(g_number_of_zones)
    for i in g_zone_id_list:
        prod_zone_index = g_zone_index_dict[i]
        for j in g_zone_id_list:
            attr_zone_index = g_zone_index_dict[j]
            total_attraction_friction[prod_zone_index] += g_zone_attraction[attr_zone_index] * \
                                                          g_friction_matrix[prod_zone_index][attr_zone_index]

    "step 2: update OD matrix"
    for i in g_zone_id_list:
        prod_zone_index = g_zone_index_dict[i]
        for j in g_zone_id_list:
            attr_zone_index = g_zone_index_dict[j]
            g_trip_matrix[prod_zone_index][attr_zone_index] = float(
                g_zone_production[prod_zone_index] * g_zone_attraction[attr_zone_index] *
                g_friction_matrix[prod_zone_index][attr_zone_index] / max(0.000001,
                                                                          total_attraction_friction[prod_zone_index]))

    # create demand.csv
    volume_list = []
    volume_rate_list=[]
    for i in range(len(o_zone_id_list)):
        od_volume = g_trip_matrix[g_zone_index_dict[o_zone_id_list[i]]][g_zone_index_dict[d_zone_id_list[i]]]
        od_volume_rate=g_trip_matrix[g_zone_index_dict[o_zone_id_list[i]]][g_zone_index_dict[d_zone_id_list[i]]]/\
                       max(0.000001,g_zone_production[g_zone_index_dict[o_zone_id_list[i]]])
        # print(od_volume_rate)
        volume_list.append(math.ceil(od_volume))
        volume_rate_list.append(od_volume_rate)

    # By Entai 2021/4/11
    print('\nTop 10 O-D Volume:')
    od_id = [i for i in range(0, len(volume_list))]
    volume_idx=sorted(enumerate(volume_list), key=lambda od_id:od_id[1], reverse = True)
    for od in range(0,10):
        index_truple = volume_idx[od]
        print('Top ' + str(od+1) + ' O/D pair: '+ \
            'zone ' + str(o_zone_id_list[index_truple[0]]) + '->zone ' + str(d_zone_id_list[index_truple[0]]) + \
                ', volume = ' + str(volume_idx[od][1]))
        logger.info('Top ' + str(od+1) + ' O/D pair: '+ \
            'zone ' + str(o_zone_id_list[index_truple[0]]) + '->zone ' + str(d_zone_id_list[index_truple[0]]) + \
                ', volume = ' + str(volume_idx[od][1]))


    data = pd.DataFrame(o_zone_id_list)
    data.columns = ["o_zone_id"]
    data["o_zone_name"] = pd.DataFrame(o_zone_name_list)
    data["d_zone_id"] = pd.DataFrame(d_zone_id_list)
    data["d_zone_name"] = pd.DataFrame(d_zone_name_list)
    data["accessibility"] = pd.DataFrame(od_distance_list)
    data["volume"] = pd.DataFrame(volume_list)

    data["volume_rate"]=pd.DataFrame(volume_rate_list)
    data["geometry"] = pd.DataFrame(od_geometry_list)

    max_OD_index = volume_list.index(max(volume_list))
    print('\nZone-to-zone OD pair with largest volume is from ' + str(o_zone_name_list[max_OD_index]) + ' to ' +
          str(d_zone_name_list[max_OD_index]))
    logger.info('Zone-to-zone OD pair with largest volume is from ' + str(o_zone_name_list[max_OD_index]) + ' to ' +
          str(d_zone_name_list[max_OD_index]))

    # print(data)
    if g_output_folder is not None:
        demand_filepath = os.path.join(g_output_folder, 'demand.csv')
        data.to_csv(demand_filepath, index=False, line_terminator='\n')
    else:
        data.to_csv('demand.csv', index=False, line_terminator='\n')

    # # update zone.csv with total production and attraction in each zone
    # data_list = [zone.id for zone in g_zone_list]
    # data_zone = pd.DataFrame(data_list)
    # data_zone.columns = ["activity_zone_id"]
    #
    # data_zone_name_list = [zone.name for zone in g_zone_list]
    # data1 = pd.DataFrame(data_zone_name_list)
    # data_zone['name'] = data1
    #
    # data_list = [zone.centroid_x for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['centroid_x'] = data1
    #
    # data_list = [zone.centroid_y for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['centroid_y'] = data1
    #
    # data_list = [zone.polygon for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['geometry'] = data1
    #
    # data_list = [zone.centroid for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['centroid'] = data1
    #
    # data_list = [zone.poi_count for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['total_poi_count'] = data1
    #
    # data_list = [zone.residential_count for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['residential_poi_count'] = data1
    #
    # data_list = [zone.office_count for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['office_poi_count'] = data1
    #
    # data_list = [zone.shopping_count for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['shopping_poi_count'] = data1
    #
    # data_list = [zone.school_count for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['school_poi_count'] = data1
    #
    # data_list = [zone.parking_count for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['parking_poi_count'] = data1
    #
    # data_list = [zone.boundary_count for zone in g_zone_list]
    # data1 = pd.DataFrame(data_list)
    # data_zone['boundary_node_count'] = data1
    #
    #
    #
    # data_zone['total_production'] = pd.DataFrame(g_total_production_list)
    # data_zone['total_attraction'] = pd.DataFrame(g_total_attraction_list)
    #
    # max_prod_o_zone_index = g_total_production_list.index(max(g_total_production_list))
    # max_attr_d_zone_index = g_total_attraction_list.index(max(g_total_attraction_list))
    # print('Origin zone with largest production volume is '+str(data_zone_name_list[max_prod_o_zone_index]))
    # print('Destination zone with largest attraction volume is ' + str(data_zone_name_list[max_attr_d_zone_index]))
    # logger.info('Origin zone with largest production volume is '+str(data_zone_name_list[max_prod_o_zone_index]))
    # logger.info('Destination zone with largest attraction volume is ' + str(data_zone_name_list[max_attr_d_zone_index]))
    #
    # # print(data_zone)
    #
    # if g_output_folder is not None:
    #     zone_filepath = os.path.join(g_output_folder, 'zone.csv')
    #     data_zone.to_csv(zone_filepath, index=False, line_terminator='\n')
    # else:
    #     data_zone.to_csv('zone.csv', index=False, line_terminator='\n')
    logger.debug("Ending RunGravityModel")



"""PART 5-2  Generate time-dependent demand by purpose-mode"""
def GenerateDemand():
    logger.debug("Starting GenerateDemand")
    global g_output_folder
    global g_distance_matrix
    global g_scaling_factor
    global g_zone_list
    global g_zone_production
    global g_zone_index_dict
    global g_purpose_mode_name_list
    global g_theta_pm_list
    global g_alpha_pm_tau
    global g_beta_pm_list
    global o_zone_id_list
    global o_zone_name_list
    global d_zone_id_list
    global d_zone_name_list
    global od_distance_list
    global od_geometry_list

    od_volume_pm = [[]]*9
    for i in range(9):
        od_volume_pm[i] = list()
    total_od_volume_list = []
    o_zone_name_list = []
    d_zone_name_list = []
    agent_list = []
    agent_id = 1

    for o_zone in g_zone_list:
        for d_zone in g_zone_list:
            o_zone_index = g_zone_index_dict[o_zone.id]
            d_zone_index = g_zone_index_dict[d_zone.id]
            o_zone_name_list.append(o_zone.name)
            d_zone_name_list.append(d_zone.name)
            od_distance_km = g_distance_matrix[o_zone_index][d_zone_index]
            od_distance_mile = od_distance_km/1.609344
            o_zone_generation = g_zone_production[o_zone_index]
            d_zone_generation = g_zone_production[d_zone_index]
            current_od_volume = 0
            for pm in range(len(g_theta_pm_list)):
                current_od_volume_pm = 0
                for tau in range(96):  # totally 96 time stamps over 24 hours splitted per 15 minutes
                    if d_zone_generation == 0:
                        T_i_pm_tau_j = 0
                    else:
                        T_i_pm_tau_j = g_scaling_factor * o_zone_generation * g_theta_pm_list[pm] * \
                                       g_alpha_pm_tau[pm][tau] * math.exp(-g_beta_pm_list[pm] * od_distance_mile)
                    current_od_volume += T_i_pm_tau_j
                    current_od_volume_pm += T_i_pm_tau_j

                    # create node-based agents
                    for i in range(math.ceil(T_i_pm_tau_j)):
                        agent = Agent()
                        agent.agent_id = int(agent_id)
                        agent.o_zone_id = int(o_zone.id)
                        agent.d_zone_id = int(d_zone.id)
                        if g_purpose_mode_name_list[pm] == 'HBW_PA' or g_purpose_mode_name_list[pm] == 'HBW_AP' or \
                                g_purpose_mode_name_list[pm] == 'HBO_PA' or g_purpose_mode_name_list[pm] == 'HBO_AP' or \
                                g_purpose_mode_name_list[pm] == 'NHB_PA' or g_purpose_mode_name_list[pm] == 'NHB_AP':
                            agent.agent_type = 'v'
                        if g_purpose_mode_name_list[pm] == 'transit':
                            agent.agent_type = 't'
                        if g_purpose_mode_name_list[pm] == 'bike':
                            agent.agent_type = 'b'
                        if g_purpose_mode_name_list[pm] == 'walk':
                            agent.agent_type = 'p'
                        agent.departure_time = g_time_stamp_name_list[tau]
                        # generate o_node_id and d_node_id randomly according to o_zone_id and d_zone_id
                        agent.o_node_id = choice(g_zone_to_nodes_dict[str(agent.o_zone_id)])
                        agent.d_node_id = choice(g_zone_to_nodes_dict[str(agent.d_zone_id)])
                        agent_list.append(agent)
                        agent_id += 1

                od_volume_pm[pm].append(current_od_volume_pm)
            # print(od_volume_pm)
            total_od_volume_list.append(current_od_volume)

    print('\nNumber of agents = ', len(agent_list))
    logger.info('Number of agents = ' + str(len(agent_list)))
    if len(agent_list) == 0:
        print('Empty agent may be caused by empty poi demand. Please check node.csv or poi_trip_rate.csv!')
        logger.warning('Empty agent may be caused by empty poi demand. Please check node.csv or poi_trip_rate.csv!')

    # print TOP 10 OD demand
    print('\nTop 10 O-D Volume:')
    od_id = [i for i in range(0, len(total_od_volume_list))]
    volume_idx = sorted(enumerate(total_od_volume_list), key=lambda od_id: od_id[1], reverse=True)
    for od in range(0, 10):
        index_truple = volume_idx[od]
        print('Top ' + str(od + 1) + ' O/D pair: ' + \
              'zone ' + str(o_zone_id_list[index_truple[0]]) + '->zone ' + str(d_zone_id_list[index_truple[0]]) + \
              ', volume = ' + str(volume_idx[od][1]))
        logger.info('Top ' + str(od + 1) + ' O/D pair: ' + \
                    'zone ' + str(o_zone_id_list[index_truple[0]]) + '->zone ' + str(d_zone_id_list[index_truple[0]]) + \
                    ', volume = ' + str(volume_idx[od][1]))

    # create demand.csv
    data = pd.DataFrame(o_zone_id_list)
    data.columns = ["o_zone_id"]
    data["o_zone_name"] = pd.DataFrame(o_zone_name_list)
    data["d_zone_id"] = pd.DataFrame(d_zone_id_list)
    data["d_zone_name"] = pd.DataFrame(d_zone_name_list)
    data["accessibility"] = pd.DataFrame(od_distance_list)
    data["total_volume"] = pd.DataFrame(total_od_volume_list)
    data["pm0_volume"] = pd.DataFrame(od_volume_pm[0])
    data["pm1_volume"] = pd.DataFrame(od_volume_pm[1])
    data["pm2_volume"] = pd.DataFrame(od_volume_pm[2])
    data["pm3_volume"] = pd.DataFrame(od_volume_pm[3])
    data["pm4_volume"] = pd.DataFrame(od_volume_pm[4])
    data["pm5_volume"] = pd.DataFrame(od_volume_pm[5])
    data["pm6_volume"] = pd.DataFrame(od_volume_pm[6])
    data["pm7_volume"] = pd.DataFrame(od_volume_pm[7])
    data["pm8_volume"] = pd.DataFrame(od_volume_pm[8])
    data["geometry"] = pd.DataFrame(od_geometry_list)

    if g_output_folder is not None:
        demand_filepath = os.path.join(g_output_folder, 'demand.csv')
        data.to_csv(demand_filepath, index=False, line_terminator='\n')
        agent_filepath = os.path.join(g_output_folder, 'simplified/input_agent.csv')
    else:
        data.to_csv('demand.csv', index=False, line_terminator='\n')
        agent_filepath = os.path.join('simplified/input_agent.csv')

    # create input_agent.csv
    local_encoding = locale.getdefaultlocale()
    with open(agent_filepath, 'w', newline='', encoding=local_encoding[1]) as fp:
        writer = csv.writer(fp)
        line = ["agent_id", "agent_type", "o_node_id", "d_node_id", "o_osm_node_id",
                "d_osm_node_id", "o_zone_id", "d_zone_id", "geometry", "departure_time"]
        writer.writerow(line)
        for agent in agent_list:
            from_node = g_node_id_to_node[agent.o_node_id]
            to_node = g_node_id_to_node[agent.d_node_id]
            o_osm_node_id = from_node.osm_node_id
            d_osm_node_id = to_node.osm_node_id
            geometry = "LINESTRING({0} {1},{2} {3})".format(round(from_node.x_coord, 7), round(from_node.y_coord, 7),
                                                            round(to_node.x_coord, 7), round(to_node.y_coord, 7))
            line = [agent.agent_id, agent.agent_type, agent.o_node_id,
                    agent.d_node_id, o_osm_node_id,
                    d_osm_node_id, agent.o_zone_id, agent.d_zone_id, geometry, agent.departure_time]
            writer.writerow(line)

    logger.debug("Ending GenerateDemand")

def GenerateDemandopmtd(split_car,split_transit,split_bike,split_walk):
    logger.debug("Starting GenerateDemandopmtd")
    global g_output_folder
    agent_id = 1
    agent_type = 'v'
    mode_num=4
    if g_output_folder is not None:
        activity_rate_filepath = os.path.join(g_output_folder, 'purpose_mode_rate.csv')
        demand_filepath = os.path.join(g_output_folder, 'demand.csv')
        zone_filepath= os.path.join(g_output_folder, 'zone.csv')
    else:
        activity_rate_filepath = 'purpose_mode_rate.csv'
        demand_filepath = 'demand.csv'
        zone_filepath='zone.csv'
    idx_list=[]
    o_id_list=[]
    d_id_list=[]
    o_name_list=[]
    d_name_list=[]
    m_id_list=[]
    m_name_list=[]
    m_rate_list=[]
    p_id_list=[]
    p_name_list=[]
    time_id_list=[]
    time_name_list=[]
    demand_odpt_list=[]
    zone_alpha_list=[]
    od_gamma_list=[]
    p_rate_list=[]
    beta_t_list=[]

    activity_rate = pd.read_csv(activity_rate_filepath)
    activity_p = activity_rate['rate']
    demand_data = pd.read_csv(demand_filepath)
    zone_data = pd.read_csv(zone_filepath)
    zone_alpha = zone_data['total_production']
    beta1 = activity_rate.iloc[1, 5:101]
    # beta=activity_rate.iloc[1,5:101]
    idx=0

    df = pd.DataFrame({'A': ['one', 'one', 'two', 'three'] * 3,
                       'B': ['A', 'B', 'C'] * 4,
                       'C': ['foo', 'foo', 'foo', 'bar', 'bar', 'bar'] * 2,
                       'D': np.random.randn(12),
                       'E': np.random.randn(12)})
    zone_number=zone_data.shape[0]
    od_number=demand_data.shape[0]

    for od in range(od_number):
        o=int(od//zone_number)
        d=int(od%zone_number)
        zone_o_alpha = zone_data['total_production'].iloc[o]
        zone_o_name = demand_data['o_zone_name'].iloc[od]
        zone_d_name = demand_data['d_zone_name'].iloc[od]
        od_gamma = demand_data['volume_rate'].iloc[od]
        for m in range(mode_num):
            m_split_mat=[split_car,split_transit,split_bike,split_walk]
            m_name_mat=['v','t','b','p']  # v for vehicle, b for bike, p for pedestrian, t for transit
            m_rate=m_split_mat[m]
            m_name=m_name_mat[m]
            for p in range(activity_p.shape[0]):
                activity_name=activity_rate.iloc[p,1]
                beta = activity_rate.iloc[p, 5:101]
                p_rate=activity_rate['rate'].iloc[p]/2
                for t in range(beta.shape[0]):
                    beta_t=beta.iloc[t]
                    time_name=beta.index.tolist()[t]
                    demand_odpt = zone_o_alpha * od_gamma * m_rate * p_rate * beta_t
                    idx=idx+1
                    idx_list.extend([idx])
                    o_id_list.extend([int(o+1)])
                    d_id_list.extend([int(d+1)])
                    o_name_list.extend([zone_o_name])
                    d_name_list.extend([zone_d_name])
                    m_id_list.extend([m+1])
                    m_name_list.extend([m_name])
                    m_rate_list.extend([m_rate])
                    p_id_list.extend([p])
                    p_name_list.extend([activity_name])
                    time_id_list.extend([t])
                    time_name_list.extend([time_name])
                    demand_odpt_list.extend([demand_odpt])
                    zone_alpha_list.extend([zone_o_alpha])
                    od_gamma_list.extend([od_gamma])
                    p_rate_list.extend([p_rate])
                    beta_t_list.extend([beta_t])
    result = pd.DataFrame({'demand_id':idx_list, 'o_zone_id':o_id_list, 'o_zone_name':o_name_list,
                           'd_zone_id':d_id_list, 'd_zone_name':d_name_list,
                           'm_id':m_id_list,'m_name':m_name_list,'p_id':p_id_list,'p_name':p_name_list,
                           'time_id':time_id_list,'departure_time':time_name_list,'volume':demand_odpt_list,
                           'zone_alpha':zone_alpha_list,'od_gamma':od_gamma_list,'m_rate':m_rate_list,
                           'p_rate':p_rate_list,'beta_t':beta_t_list})
    demand_time_filepath=os.path.join(g_output_folder, 'demand_time.csv')
    # demand_time_sample_filepath=os.path.join(g_output_folder, 'demand_time_sample.csv')
    # result_sample=result[result['id']<=25921*4]
    result.to_csv(demand_time_filepath, index=False, encoding="utf-8")
    # result_sample.to_csv(demand_time_sample_filepath,  encoding="utf-8")
    logger.debug("Ending GenerateDemandopmtd")


"""PART 6  GENERATE AGENT"""
agent_list = []
def GenerateAgentBasedDemand():
    logger.debug("Starting GenerateAgentBasedDemand")
    # print(g_zone_to_nodes_dict)
    global g_output_folder
    agent_id = 1
    # agent_type = 'v'
    if g_output_folder is not None:
        demand_filepath = os.path.join(g_output_folder, 'demand_time.csv')
        agent_filepath = os.path.join(g_output_folder, 'simplified/input_agent.csv')
    else:
        demand_filepath = 'demand_time.csv'
        agent_filepath = 'simplified/input_agent.csv'

    with open(demand_filepath, 'r', errors='ignore') as fp:
        reader = csv.DictReader(fp)
        for line in reader:
            for i in range(math.ceil(float(line['volume']))):
                agent = Agent()
                agent.agent_id = int(agent_id)
                agent.o_zone_id = int(line['o_zone_id'])
                agent.d_zone_id = int(line['d_zone_id'])
                agent.agent_type = line['m_name']
                agent.departure_time = line['departure_time']
                # generate o_node_id and d_node_id randomly according to o_zone_id and d_zone_id
                agent.o_node_id = choice(g_zone_to_nodes_dict[str(agent.o_zone_id)])
                agent.d_node_id = choice(g_zone_to_nodes_dict[str(agent.d_zone_id)])
                agent_list.append(agent)
                agent_id += 1
    print('\nNumber of agents = ', len(agent_list))
    logger.info('Number of agents = '+str(len(agent_list)))
    if len(agent_list) == 0:
        print('Empty agent may be caused by empty poi demand. Please check node.csv or poi_trip_rate.csv!')
        logger.warning('Empty agent may be caused by empty poi demand. Please check node.csv or poi_trip_rate.csv!')

    local_encoding = locale.getdefaultlocale()
    with open(agent_filepath, 'w', newline='', encoding=local_encoding[1]) as fp:
        writer = csv.writer(fp)
        line = ["agent_id", "agent_type", "o_node_id", "d_node_id", "o_osm_node_id",
                "d_osm_node_id", "o_zone_id", "d_zone_id", "geometry", "departure_time"]
        writer.writerow(line)
        for agent in agent_list:
            from_node = g_node_id_to_node[agent.o_node_id]
            to_node = g_node_id_to_node[agent.d_node_id]
            o_osm_node_id = from_node.osm_node_id
            d_osm_node_id = to_node.osm_node_id
            # time_stamp = math.ceil(random.uniform(1, 60))
            # if time_stamp == 60:
            #     departure_time = "0800"
            # else:
            #     if time_stamp < 10:
            #         departure_time = "070" + str(time_stamp)
            #     else:
            #         departure_time = "07" + str(time_stamp)
            geometry = "LINESTRING({0} {1},{2} {3})".format(round(from_node.x_coord, 7), round(from_node.y_coord, 7),
                                                            round(to_node.x_coord, 7), round(to_node.y_coord, 7))
            line = [agent.agent_id, agent.agent_type, agent.o_node_id,
                    agent.d_node_id, o_osm_node_id,
                    d_osm_node_id, agent.o_zone_id, agent.d_zone_id, geometry, agent.departure_time]
            writer.writerow(line)
    logger.debug("Ending GenerateAgentBasedDemand")
    # comments:
    # Please visit https://github.com/dabreegster/grid2demand/blob/scenario_script/src/demand_to_abst_scenario.py for simulation in AB Street
