# GRID2DEMAND: A tool for generating zone-to-zone travel demand based on grid zones

**Template Code and Test Data Set: https://github.com/EntaiWang99/Grid2Demand/tree/main/test_file**

*Please Visit: https://pypi.org/project/grid2demand/0.0.0.24/*

*Email: entaiwang@bjtu.edu.cn*

## 1. What is GRID2DEMAND?
GRID2DEMAND is a quick trip generation and distribution tool based on the four-step travel model. First, the research region is divided into grid zones of the same scale. POI nodes are used to generate node production/attraction. Second, trip distribution is achieved by a typical gravity model.

### 1.1. Data files
Input files are the network files in GMNS format (node.csv, link.csv, poi.csv), which can be automatically generated by the OSM2GMNS tool. Node and POI files will be used for generating demand, and poi.csv may need manual edition.
Output files are zone.csv, accessibility.csv, poi_trip_rate.csv, and demand.csv. Final zone-to-zone demand is listed in demand.csv with geometry.


### 1.2. Grid partition
Grids are automatically generated by a given scale of degree or number of zones in the research region. Each grid is regarded as TAZ used for trip generation and distribution. The grid information is stored in zone.csv.


### 1.3. Node demand
All types of POI nodes are collected from poi.csv. The values of production and attraction under each trip purpose and POI type are defined by default or by users. Therefore, the production and attraction values of each node can be calculated. The POI node production/attraction rates used in the model are summarized in poi_trip_rate.csv. The node information is updated in node.csv.


### 1.4. Accessibility
Accessibility is measured by zone-to-zone distance according to zone centroid coordinates. A degree at different latitudes represents different lengths on a flat surface. According to a given latitude, the closest latitude in the following table is selected to calculate the longitudinal length.

### 1.5. Gravity model
For each OD pair, a typical gravity model is applied to calculate zone-to-zone demand volume. 

**The framework of GRID2DEMAND is illustrated in the following figure.**

![](img/1.jpg)

## 2. How to use GRID2DEMAND?
We will use University of Maryland, College Park as an example to illustrate how to use GRID2DEMAND.

**Step 1: Determine the research boundary and download .osm file from OpenStreetMap**
Adjust the map to the location of interest and click on the Export1 button on the top.

![](2.1.jpg)

Then, obtain the latitude and longitude coordinates (users can manually select a different area2). Lastly, click on the Export3 button found in the middle of the navigator to download an OSM data file. For a very large area of interest, users need to click the link of “Overpass API” to obtain a map file.

![](img/2.2.jpg)

**Step 2: Execute OSM2GMNS to get network files in GMNS format**
Open the Python IDE such as Pycharm for a typical configuration. Then, OSM2GMNS converts map.osm file in OSM format into a network file in GMNS format.
```python
import osm2gmns as og
net = getNetFromOSMFile(r'map.osm', network_type = ('railway', 'aeroway', 'auto', 'walk', 'bike'), POIs = True, defaults_lanes = True, default_speed = True)
og.connectPOIWithNet(net)
og.outputNetToCSV(net, output_folder)
```

![](img/2.3.jpg)

Please note that poi.csv may need to be edited manually in case of information loss。

**Step 3: Execute GRID2DEMAND Python code**
(1)Import the package and read input network data
```python
import grid2demand as gd
gd.readNetworkFile("./data_folder")
```
(2)Network partition into grids
User can customize the number of grids by setting “number_of_x_blocks” and “number_of_y_blocks”. As well, user can customize grid’s length and width in degree of longitude and latitude by setting “scale_x” and “scale_y”. By default, “scale_x” and “scale_y” are set as 0.006.
```python
gd.NetworkPartition(number_of_x_blocks = 5, number_of_y_blocks = 5)
or：
gd.NetworkPartition(scale_x = 0.005, scale_y = 0.005)
```

(3)Get production/attraction rates of each land use type with a specific trip purpose
User can customize or edit poi_trip_rate.csv by adding the folder location and customize trip purpose. By default, trip purpose is set as “HBW”.
```python
gd.getPoiTripRate(trip_rate_folder = None, trip_purpose = None)
```

(4)Define production/attraction value of each node according to POI type
```python
gd.getNodeDemand()
```

(5)Calculate zone-to-zone accessibility matrix by centroid-to-centroid straight distance
User can customize the latitude of the research area. The script will match the closest latitude to calculate the longitudinal length in kilometer according to 1.4. The degree of 30 is selected as default.
```python
gd.AccessMatrix(latitude=30)
```

(6)Apply gravity model to conduct trip distribution
```python
gd.GravityModel()
```

(7)Output zone.csv, poi_trip_rate.csv, accessibility.csv, demand.csv and update node.csv, poi.csv
```python
gd.outputCSV("./data_folder")
```

Configurate working dictionary in the Python IDE (e.g., Pycharm). Then, execute GRID2DEMAND to get zone-to-zone demand, generating four files which are highlighted in blue. 

![](img/4.1.jpg)

**Step 4: Visualization in QGIS**
Open QGIS and add Delimited Text Layer of the output files.

![](img/4.2.jpg)

Then Open the Properties window of the demand layer. Set the symbology as graduated symbols by size.

![](img/4.3.jpg)

Zone-to-zone demand can be visualized with a base map.

![](img/4.4.jpg)

