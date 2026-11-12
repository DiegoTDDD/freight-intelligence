README for "Freight Analysis Framework, FAF5, HiLoForecasts" dataset. 
U.S. Department of Transportation (USDOT), Bureau of Transportation Statistics (BTS)
2023-09-29

----------------------------------------------------------------
LINKS TO DATASET
----------------------------------------------------------------
A. ROSA-P archive dataset link (2017-Present and high, medium, and low forecasts through 2050): 

	https://doi.org/10.21949/1529116


----------------------------------------------------------------
SUMMARY OF DATASET
----------------------------------------------------------------
The Freight Analysis Framework (FAF) creates a comprehensive picture of freight movement among states and major metropolitan areas by all modes of transportation. The FAF integrates data from a variety of sources. Starting with data from the Commodity Flow Survey (CFS) and international trade data from the Census Bureau, FAF incorporates data from agriculture, extraction, utility, construction, service, and other sectors.

The FAF5 Regional Database of tonnage, value, and ton-miles by FAF regions of origin and destination, commodity type, and mode, benchmarked to the 2017 Commodity Flow Survey is available. Weights are in thousands of tons, activity is in millions of ton-miles, and values are in millions of 2017 constant dollars. Files are available for download in .csv and MS Access formats on <<https://www.bts.gov/faf>> and <<https://faf.ornl.gov/faf5/>>. An online Data Tabulation Tool (DTT), which uses the FAF data to create tabular summaries and visualizations for users, is also provided. 

State-level databases are also provided. These databases are derived from the regional databases. Tonnage, value, and ton-miles by origin state and destination state are provided. 

The current version of FAF provides estimates for tonnage, value, and ton-miles by origin-destination pair of FAF regions, commodity type, and mode for:
•	Base year (Y)
•	Annual estimates (Y + 1 through Y + 4)
•	Forecast year estimates (Y + 5, Y + 6, Y + 7 and Y + 8 through Y + 28 in 5-year increments)
•	Historical trend estimates (1997 through Y – 5; State-level only)

FAF versions are denoted using a, b and c as in FAFa.b.c. Version ID is determined as follows. A new version of FAF is initiated every five years in year Y, in years ending 2 and 7. The first digit, a, in the version ID corresponds to this. For example, the first version of FAF was developed for commodity flows in year 1997 and FAF1 refers to this release, while FAF5 refers to the 2017-based version. 
•	Base year 1997: FAF1
•	Base year 2002: FAF2
•	Base year 2007: FAF3
•	Base year 2012: FAF4
•	Base year 2017: FAF5

The second digit, b, of the FAF version ID corresponds to major, planned release dates within the five year cycle. At this time, the following notation is used with b denoting what has been added in the release:
•	1 (e.g., FAF 5.1): annual estimates for Y+1 and an updated DTT
•	2: annual estimates for Y+2, an updated DTT, and forecast year estimates
•	3: truck flow network assignments for Y and Y+28, ton-mile estimates for all years, and an updated DTT
•	4: annual estimates for Y+3 and an updated DTT
•	5: annual estimates for Y+4 and an updated DTT

The version identifier c is used for other updates in between FAFa.b releases. The a.b.c versions cover preliminary annual estimates as well as adjustments such as data improvements or corrections. “Major” releases are FAFa.b releases; all other releases are “minor”. 
The main websites, <<https://www.bts.gov/faf>> and <<https://faf.ornl.gov/faf5/>>, contain several documentation items:
•	A User Guide
•	A DTT guide called the “Getting Started Guide”
•	A detailed methodology that describes the FAF data development 

Each downloadable regional or state-level database contains a Metadata file. This file provides a data dictionary for the geographic regions, commodity types, and mode codes that appear in the database. 

The website <<https://ops.fhwa.dot.gov/freight/freight_analysis/faf/>> contains the FAF5 Forecasts Report (PDF), which documents the commodity flow forecast development process. 

Detailed documentation is currently being prepared for the Annual Estimates development process, ton-mile estimation, and the historical trends (reprocessed state-level data) development process. 

----------------------------------------------------------------
TABLE OF CONTENTS
----------------------------------------------------------------

A. General Information
B. Sharing/Access & Policies Information
C. Data and Related File Overview
D. Methodological Information
E. Data-Specific Information for: Freight Analysis Framework, FAF5, HiLoForecasts [datasets]
F. Update Log



----------------------------------------------------------------
A. GENERAL INFORMATION
----------------------------------------------------------------

0. Title of Dataset: 
   Freight Analysis Framework, FAF5, HiLoForecasts [datasets]


1. Description of Dataset:
The Freight Analysis Framework (FAF) creates a comprehensive picture of freight movement among states and major metropolitan areas by all modes of transportation. The FAF integrates data from a variety of sources. Starting with data from the Commodity Flow Survey (CFS) and international trade data from the Census Bureau, FAF incorporates data from agriculture, extraction, utility, construction, service, and other sectors. 


2. Dataset archive link: 
       https://doi.org/10.21949/1529116


3. Authorship Information:Principal Data Creator or Data Manager Contact Information
      Name: Office of Statistical and Economic Analysis (OSEA)
      Institution: U.S. Department of Transportation, Bureau of Transportation Statistics (BTS)
      Address: 1200 New Jersey Ave. SE, Washington D.C. 20590
      Email: FAF@dot.gov

   Data Distributor Contact Information
      Name: Office of Statistical and Economic Analysis (OSEA)
      Institution: U.S. Department of Transportation, Bureau of Transportation Statistics (BTS)
      Address: 1200 New Jersey Ave. SE, Washington D.C. 20590
      Email: FAF@dot.gov
	   
	   
4. Date of data collection and update interval:
   The benchmark version, forecasts, and reprocessed historical data are produced every five years. Data for intervening years are updated annually.


5. Geographic location of data collection: 
   United States of America


6. Information about funding sources that supported the collection of the data:
   U.S. Department of Transportation, Bureau of Transportation Statistics (BTS), Federal Highway Administration (FHWA)


----------------------------------------------------------------
B. SHARING/ACCESS & POLICIES INFORMATION 
----------------------------------------------------------------

0. Recommended citation for the data: 
     U.S. Department of Transportation, Bureau of Transportation Statistics (BTS), Federal Highway Administration (FHWA). (2017) Freight Analysis Framework, FAF5, HiLoForecasts[datasets].https://doi.org/10.21949/1529116

1. Licenses/restrictions placed on the data:
   These data are in the Public Domain.


2. Was data derived from another source?:
   Yes. Details about the input sources are in the methodology report, https://doi.org/10.2172/1844893.
   
3. This document was created to meet the requirements enumerated in the U.S. Department of Transportation's 'Plan to Increase Public Access to the Results of Federally-Funded Scientific Research' Version 1.1 << https://doi.org/10.21949/1520559 >> and guidelines suggested by the DOT Public Access website << https://doi.org/10.21949/1503647  >>, in effect and current as of December 03, 2020.




----------------------------------------------------------------
C. DATA & RELATED FILE OVERVIEW
----------------------------------------------------------------

1. File List for the FAF5.5_HiLoForecasts.zip collection        

   A. Filename: 
      bts_FAF_HiLoForecasts_DMP_20230929.pdf
           Short description: 
           A PDF file containing the Data Management Plan that was created for current and future management of the data and associated files. 
 
   B. Filename: 
      bts_FAF_HiLoForecasts_README_20230929.txt       
            Short description: 
            The README.txt file that includes human-readable information about the data, variable definitions, contact information, and other contextual information. The file you are reading now.    

   C. Filename:
       FAF5.5_HiLoForecasts.csv
	Short description:
	A CSV file containing the commodity flow data for FAF regional origins and destinations for 2017-present and high, medium, and low forecasts for 2023-2050. 

   D. Filename: 
       FAFX_metadata.xlsx
            Short description: 
            A Microsoft Excel file containing a data dictionary, listing names, definitions, and formats of variables.
 
----------------------------------------------------------------
D. METHODOLOGICAL INFORMATION
----------------------------------------------------------------

1. Description of methods used for collection/generation of data: 
   The FAF benchmark methodology report is here: https://doi.org/10.2172/1844893
   Methodology reports for the annual estimates and reprocessed historical data are in progress. 

2. Instrument- or software-specific information needed to interpret the data:
   The data can be opened and analyzed using any program (such as R or SAS) that can read in millions of records.
   The metadata file can be opened with Microsoft Excel.
   The documentation files can be opened with a PDF viewer. 

----------------------------------------------------------------
E. DATA-SPECIFIC INFORMATION  
----------------------------------------------------------------

1. FAF5.5.1_HiLoForecasts.csv data table
   The benchmark, forecast, and historical reprocessed estimates are updated every five years.  Data is updated annually. Any metadata updates are performed at the same time. For the most recent data, please visit the BTS FAF website at https://www.bts.gov/faf 

A. Number of variables (columns):
   82

B. Data Dictionary/Variable List:
   Because of the large number of variables, please refer to the Data Dictionary found within the file FAFX_metadata.xlsx for names, definitions, and formats of variables.

C. Missing data codes:
   None




----------------------------------------------------------------
F. UPDATE LOG
----------------------------------------------------------------

This bts_FAF_HiLoForeasts_README_20230929.txt file was originally created on 2023-09-29 by Monique Stinson, Freight Estimation, Forecasting, and Analysis Manager, monique.stinson@dot.gov
 
2023-09-29: Original file created





