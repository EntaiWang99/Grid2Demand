# import osm2gmns as og
# net = og.getNetFromOSMFile('map.osm', network_type=('railway', 'auto', 'bike', 'walk'), POIs=True, default_lanes=True,default_speed=True)
# og.connectPOIWithNet(net)
# og.generateNodeActivityInfo(net)
# og.outputNetToCSV(net)

import grid2demand_0525a as gd
import os

os.chdir('./Norfolk_VA')
"Step 1: Read Input Network Data"
gd.ReadNetworkFiles()
# gd.ReadExternalPOI()
# users can give external customized_poi.csv

"Step 2: Partition Grid into cells"
gd.PartitionGrid(number_of_x_blocks=None, number_of_y_blocks=None, cell_width=500, cell_height=500, external_poi=True)
# users can customize number of grid cells or cell's width and height
# Also partition grid for external poi

"Step 3: Simplify the network for path4gmns"
gd.SimplifyNet(link_type_set = {'primary', 'secondary'}, criteria=10)
# users can customize 1) the link types in the simplified network
# and 2) maximum number of poi nodes in each zone by area
# we need to use the simplified network to define trip generation for boundary nodes

gd.GeneratePOIConnector()
# connect useful POI nodes to the network

"Step 4: Get Trip Generation Rates of Each Land Use Type"
gd.GetPoiTripRate()
# users can customize poi_trip_rate.csv for each land use type

"Step 5: Define Production/Attraction Value of Each Node According to POI Type and Activity Purpose"
gd.GetNodeDemand(residential_generation=200, boundary_generation=5000)
# users can customize the values of trip generation for residential nodes and boundary nodes

"Step 6: Calculate Zone-to-zone Accessibility Matrix by Centroid-to-centroid Straight Distance"
gd.ProduceAccessMatrix()

"Step 7: Generate Time-dependent Demand and Agent by Purpose-mode"
gd.GenerateDemand()
