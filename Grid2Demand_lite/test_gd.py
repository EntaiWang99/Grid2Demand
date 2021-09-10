import grid2demand_0712a_lite as gd
import os

### obtain the network in GMNS format by osm2gmns ###
os.chdir("./gansu")
# import osm2gmns as og
# net = og.getNetFromFile('gansu-latest.pbf',network_type=('auto'),POIs=True,default_lanes=True,default_speed=True)
# og.connectPOIWithNet(net)
# og.generateNodeActivityInfo(net)
# og.outputNetToCSV(net)


"Step 1: Read Input Network Data"
gd.ReadNetworkFiles()

"Step 2: Partition Grid into cells"
gd.PartitionGrid(number_of_x_blocks=100, number_of_y_blocks=100, cell_width=None, cell_height=None)
# user can customize number of grid cells or cell's width and height






"Step 3: Get Production/Attraction Rates of Each Land Use Type with a Specific Trip Purpose"
gd.GetPoiTripRate(trip_purpose=1)
# user can customize poi_trip_rate.csv and trip purpose

"Step 4: Define Production/Attraction Value of Each Node According to POI Type"
gd.GetNodeDemand(residential_production=10, residential_attraction=10, boundary_production=5, boundary_attraction=5)

"Step 5: Calculate Zone-to-zone Accessibility Matrix by Centroid-to-centroid Straight Distance"
gd.ProduceAccessMatrix()
# user can customize the latitude of the research area and accessibility.csv

"Step 6: Apply Gravity Model to Conduct Trip Distribution"
gd.RunGravityModel(population=320, AvgTripRatePerPerson=2.3, trip_purpose=1, a=None, b=None, c=None)
# user can customize 1) population of the area of interest and average trip rate per person to control total trips; and
# 2) friction factor coefficients under a specific trip purpose

"Step 7: Generate Agent"
gd.GenerateAgentBasedDemand()
