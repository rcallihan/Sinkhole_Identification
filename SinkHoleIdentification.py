import arcpy, os, re
from arcpy import env
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")
arcpy.env.overwriteOutput = True

#input variables 

DEM = arcpy.GetParameterAsText(0)
d = arcpy.GetParameterAsText(1)
HOLV = arcpy.GetParameterAsText(2)
workspace = arcpy.GetParameterAsText(3)

arcpy.env.workspace = workspace
arcpy.env.snapRaster = DEM
arcpy.env.extent = DEM

arcpy.AddMessage("======================================")
arcpy.AddMessage("Starting Sinkhole Identification Tool")
arcpy.AddMessage("======================================") 

arcpy.AddMessage("")
arcpy.AddMessage("Input parameters:")
arcpy.AddMessage("DEM: %s" % DEM)
arcpy.AddMessage("Minimum depth threshold (d): %s" % d) 

#get spatial reference from DEM
DEM_sr = arcpy.Describe(DEM).spatialReference

#creating
HOLV += ".shp"
arcpy.CreateFeatureclass_management(workspace, HOLV, "POLYGON", "", "", "", DEM_sr, "", "", "", "")
arcpy.AddField_management(HOLV, "GRIDCODE", "DOUBLE", 10, "", "", "", "NON_NULLABLE")

loop_num = 1
flag = True
while flag: 	
	arcpy.AddMessage("==============Iteration #%s============" % loop_num)

	# 1) [Fill Sinks] Fill sinks (DEM ‡FIL)
	arcpy.AddMessage("Step 1: Filling sinks...")
	outFill = Fill(DEM)
	outFill.save("filled_DEM")

	# 2) [Raster Calculator] Create a sink depth map (SNK)
	arcpy.AddMessage("Step 2: Creating a sink depth map...")
	sink = Raster("filled_DEM") - Raster(DEM)
	sink.save("sink")
	SNK = Con(("sink") > 0, "sink")
	SNK.save("snk")

	# 3) [Raster Calculator] Create mask layer of ones (MSK) for SNK
	arcpy.AddMessage("Step 3: Creating mask layer of ones for SNK")
	MSK = Con(SNK > 0, 1)
	MSK.save("msk")

	#4) [Raster to Polygon] Convert MSK to polygon (MSKV). Do not use “Simplify Polygons” option.
	arcpy.AddMessage("Step 4: Raster MSK to polygon MSKV...")
	arcpy.RasterToPolygon_conversion("msk", "mskv.shp", "NO_SIMPLIFY")

	# 5) [Zonal Statistics] Create a zone maximum raster (MAX), where MSKV polygons are the zones 
	arcpy.AddMessage("Step 5: Creating zonal MAX of SNK where zones = MSKV.shp...")
	zonalmax = ZonalStatistics("mskv.shp", "ID", "snk", "MAXIMUM", "NODATA")
	zonalmax.save("MAX")

	# 6) [Raster Calculator] Create hole indicator raster (HOL) for sinks having at least the minimum 
	arcpy.AddMessage("Step 6: Creating hole indicator raster (HOL) for sinks with the specified min depth (d)...")
	HOL = Con(Raster("snk") >= float(d), Con(Raster("snk") == Raster("MAX"), 1))
	HOL.save("HOL")


	nodata = arcpy.GetRasterProperties_management("hol", "ALLNODATA")
	isnodata = nodata.getOutput(0)
	#arcpy.AddMessage(str(isnodata))
	if int(isnodata) == 1:
		arcpy.AddMessage(" No data in raster \"hol\". Process stopped.")
	  	arcpy.AddMessage("======================================")
		arcpy.AddMessage("Sinkhole identifiation complete.")
		arcpy.AddMessage("======================================")
		break

	# 7) [Raster to Polygon] Convert HOL to polygon (HOLV1). Do not use “Simplify Polygons” option.
	arcpy.AddMessage("Step 7: Converting HOL to polygon (HOLV1)...")
	arcpy.RasterToPolygon_conversion("HOL", "HOLV1.shp", "NO_SIMPLIFY")

	# 8) If HOLV1 is empty, then BREAK [not sure the easiest way to check for this in Python; in MATLAB, 
	arcpy.AddMessage("Step 8: Checking number of polygons in HOLV1...")
	num_records = int(arcpy.GetCount_management("HOLV1.shp").getOutput(0))
	arcpy.AddMessage("	Number of records: %s" % (num_records))

	# 9) Update HOLV such that HOLV = merge(HOLV1, HOLV).
	arcpy.AddMessage("Step 8: Merging HOLV and HOLV1...")
	#arcpy.Merge_management(["HOLV.shp", "HOLV1.shp"], "HOLV_merge.shp")
	arcpy.Append_management("HOLV1.shp", HOLV, "NO_TEST")

	# 10) [Raster Calculator] Create inverted sink depth raster with holes removed (DEM2):
	arcpy.AddMessage("Step 10: Inverting sink depth raster and remove holes removed...")
	DEM2 = Con(Raster("MAX") >= float(d), Con(Raster("snk") != Raster("MAX"), Raster("MAX") - Raster("snk")))
	DEM2.save("DEM2")

	# 11) Set DEM = DEM2 and go back to Step 1
	DEM = "DEM2"

	loop_num += 1

	arcpy.AddMessage("======================================")
	arcpy.AddMessage("") 

def cleanup():
	arcpy.AddMessage("Cleaning up intermediate files...")
	for filename in ["filled_DEM", "sink", "snk", "MAX", "msk", "DEM", "DEM2", "mskv.shp", "hol", "HOLV1.shp"]:
		if arcpy.Exists(filename):
			arcpy.Delete_management(filename)

cleanup()