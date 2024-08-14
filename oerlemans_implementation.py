import requests
import pandas
import pathlib
import cdsapi
from typing import List
import netCDF4
import janitor


# TODO: Cleanup code.
#  Find better approach for data generation. This is messy. Should not be this way.
#  Manually creating required dataset could be better.
#  May not need to populate each year with ppt values.

# ======================================================================================================================
# Overall process.
# Get initial data about 'Reference glaciers'
# Get precipitation data for these glaciers. ERA5 used.
# Proceed to solving equation.
# ======================================================================================================================

# Set this to download folder, if not then current working directory.
DOWNLOAD_FOLDER_PATH = pathlib.Path.cwd()

# Reference glacier data is available at what url.
reference_glacier_excel_file_url = 'http://wgms.ch/downloads/REF-Glaciers_all_2018-11.xlsx'

# Download only once.
if not pathlib.Path.is_file(pathlib.Path.joinpath(DOWNLOAD_FOLDER_PATH, 'ref_glac_excel_data.xlsx')):
    response = requests.get(reference_glacier_excel_file_url)
    with open('ref_glac_excel_data.xlsx', 'wb') as fileObject:
        fileObject.write(response.content)

# FIRST DATA MANIPULATION AND CLEANUP
# ======================================================================================================================

# Read and cleanup data from the Excel file
filepath = pathlib.Path.joinpath(DOWNLOAD_FOLDER_PATH, 'ref_glac_excel_data.xlsx')
xl = pandas.ExcelFile(filepath)
# print(xl.sheet_names)

# Glacier id, lat and lon are on the sheet 'general information'
df1 = pandas.read_excel(xl, sheet_name='General Information')
df1 = df1[['WGMS_ID', 'LATITUDE', 'LONGITUDE']]

# Other glacier params are on 'State'  sheet
df2 = pandas.read_excel(xl, sheet_name='State')

# Only retain useful columns
df2 = df2[['NAME', 'WGMS_ID', 'YEAR', 'HIGHEST_ELEVATION', 'LOWEST_ELEVATION', 'LENGTH']]

# merge lat lon values from previous dataframe
df2 = df2.merge(df1, on='WGMS_ID')

# Sort by 'WGMS_ID'
df2 = df2.sort_values(by=['WGMS_ID', 'YEAR'])
df2 = df2.reset_index(drop=True)

# If missing interpolate 'HIGHEST_ELEVATION' and 'LOWEST_ELEVATION'. First linearly interpolate to fill intermediate
df2['HIGHEST_ELEVATION'] = df2.groupby('WGMS_ID')['HIGHEST_ELEVATION'].apply(lambda group:group.interpolate()).reset_index()['HIGHEST_ELEVATION']
df2['LOWEST_ELEVATION'] = df2.groupby('WGMS_ID')['LOWEST_ELEVATION'].apply(lambda group:group.interpolate()).reset_index()['LOWEST_ELEVATION']

# Interpolate Length as well.
df2['LENGTH'] = df2.groupby('WGMS_ID')['LENGTH'].apply(lambda x: x.interpolate()).reset_index()['LENGTH']

# If there are still na values in elevation and length columns drop them.
df2 = df2[df2['HIGHEST_ELEVATION'].notna()]
df2 = df2[df2['LOWEST_ELEVATION'].notna()]
df2 = df2[df2['LENGTH'].notna()]
df2 = df2.reset_index(drop=True)

# Calculate slope. 'LENGTH' is in km. Elevation in meters. oerlemans required length to be in m.
df2['LENGTH'] = df2['LENGTH'] * 1000
df2['SLOPE'] = (df2['HIGHEST_ELEVATION'] - df2['LOWEST_ELEVATION']) / (df2['LENGTH'])

# Remove data with too few length values. i.e. these glaciers do not have more than 10 [arbitrary] 'LENGTH' record.
# Calculating 'length change' will not be possible.
df2 = df2.groupby('WGMS_ID').filter(lambda x: len(x) > 10).reset_index(drop=True)

# Give proper name. df1 and df2 will not be used further. Too Confusing. Use better variable names before. Temporary.
glacier_data = df2

# Get min and max year. This is to download era5 data.
glacier_data['MIN_YEAR'] = glacier_data.groupby('WGMS_ID')['YEAR'].transform('min')
glacier_data['MAX_YEAR'] = glacier_data.groupby('WGMS_ID')['YEAR'].transform('max')

# Add missing 'years'. This is done to populate precipitation data at each year later.
# TODO: Why am I doing this? Do I actually need to do this.
# ======================================================================================================================


def fill_missing_year(dataframe):
    return pandas.RangeIndex(start=dataframe.YEAR.min(), stop=dataframe.YEAR.max() + 1, name='YEAR')


# Fill missing year for each glacier. Just the year other values are Nan
glacier_data = glacier_data.complete(fill_missing_year, by='WGMS_ID', sort=True)

# Group this and fill known values. bfill and ffill should be safe. these are repeating values. values do not change.
# TODO: There is a parameter for the .complete function that can do the following in one go. todo later.
glacier_data['NAME'] = glacier_data.groupby('WGMS_ID')['NAME'].apply(lambda x: x.ffill().bfill()).reset_index(drop=True)
glacier_data['LATITUDE'] = glacier_data.groupby('WGMS_ID')['LATITUDE'].apply(lambda x: x.ffill().bfill()).reset_index(drop=True)
glacier_data['LONGITUDE'] = glacier_data.groupby('WGMS_ID')['LONGITUDE'].apply(lambda x: x.ffill().bfill()).reset_index(drop=True)
glacier_data['MIN_YEAR'] = glacier_data.groupby('WGMS_ID')['MIN_YEAR'].apply(lambda x: x.ffill().bfill()).reset_index(drop=True)
glacier_data['MAX_YEAR'] = glacier_data.groupby('WGMS_ID')['MAX_YEAR'].apply(lambda x: x.ffill().bfill()).reset_index(drop=True)

# Interpolate the 'ELEVATION' data again.
# If missing interpolate 'HIGHEST_ELEVATION' and 'LOWEST_ELEVATION'. First linearly interpolate to fill intermediate
# Then do index to fill rest
# If first values are na, then do a backward fill.
glacier_data['HIGHEST_ELEVATION'] = glacier_data.groupby('WGMS_ID')['HIGHEST_ELEVATION'].apply(lambda group:group.interpolate()).reset_index()['HIGHEST_ELEVATION']
glacier_data['LOWEST_ELEVATION'] = glacier_data.groupby('WGMS_ID')['LOWEST_ELEVATION'].apply(lambda group:group.interpolate()).reset_index()['LOWEST_ELEVATION']

# Interpolate Length values as well. Default is linear. Pass otehr if needed.
# TODO: LOOK INTO PYJANITOR DOCUMENTATION.
glacier_data['LENGTH'] = glacier_data.groupby('WGMS_ID')['LENGTH'].apply(lambda x:x.interpolate()).reset_index()['LENGTH']

# Calculate 'SLOPE' again.
glacier_data['SLOPE'] = (glacier_data['HIGHEST_ELEVATION'] - glacier_data['LOWEST_ELEVATION']) / glacier_data['LENGTH']

# Calculate 'Reference Length'
# This is done differently in paper. I think oerlemans used 1950 glacier length. Here average for whatever data is
# available is used as reference length.
glacier_data['REFERENCE_LENGTH'] = glacier_data.groupby('WGMS_ID')['LENGTH'].transform('mean')

# Calculate L'
glacier_data['L_prime'] = glacier_data['REFERENCE_LENGTH'] - glacier_data['LENGTH']

# SECOND DATA MANIPULATION AND CLEANUP
# ======================================================================================================================
# Okay. ERA5 data download. For precipitation.
# Signup at the new cds thing
# Get api keys. Follow this guide: https://cds.climate.copernicus.eu/api-how-to
# Save the credentials for api request to a file called '.cdsapirc' to $HOME folder. -> usually 'C:/Users/{username}/'
# SWITCH TO LINUX. issues with grib file handling and others...
# Using netcdf for now
# ======================================================================================================================

def download_era5(location: List[float],
                  wgms_id: int,
                  year1: int,
                  year2: int,
                  data_name: str = 'reanalysis-era5-single-levels-monthly-means'):

    # Define filename here and check if exists. If it does not, then download.
    filename = pathlib.Path.joinpath(DOWNLOAD_FOLDER_PATH, str(wgms_id)+'_'+str(year1)+'_'+str(year2)+'.nc')

    # Generate a list of years to feed into the api request.
    year = [_ for _ in range(year1, year2 + 1)]

    # Check. Download data only once.
    if not pathlib.Path.is_file(filename):

        # Do you have to close this? Read Documentaiton.
        client_object = cdsapi.Client()

        # ERA5 requires an area. So point location data is not possible. Hack: duplicate lat lon.
        area = [location[0], location[1], location[0], location[1]]

        # TODO: understand era5 data better. 'monthly-means' downloaded. daily better?
        #  Are you downloading correct data?
        #  Monthly means selected because paper says 'climatological' data was used. Meaning averaged?
        client_object.retrieve(
            data_name,
            {
                'format': 'netcdf',
                'variable': 'total_precipitation',
                'month': [
                    '01', '02', '03',
                    '04', '05', '06',
                    '07', '08', '09',
                    '10', '11', '12',
                ],
                'year': year,
                'product_type': 'monthly_averaged_reanalysis',
                'time': '00:00',
                'area': area,
            },
            filename)
        print(filename, '... Downloaded')
        return 1
    else:
        print('... exists!')
        return 0


def generate_annual_data(nc_filepath, wgms_id):
    annual_precip = []

    # Do you have to close this? Read documentation.
    # TODO: consider 'with'.
    nc_dataset = netCDF4.Dataset(nc_filepath)

    # Read date. Date is int with format 'yyyymmdd'. Manipulate as date later.
    ncfile_date_data = nc_dataset['date'][:]  # this particular dataset has 'date' not 'time'.
    ncfile_ppt_data = nc_dataset['tp'][:]  # ppt values under variable name 'tp'. ERA5 specific.

    # Create a list fist, convert to pandas dataframe to use its 'groupby' to get annual data
    for i, j in zip(ncfile_date_data, ncfile_ppt_data):
        annual_precip.append([i, j[0][0]])

    annual_precip_dataframe = pandas.DataFrame(annual_precip, columns=['DATE', 'PPT_MONTHLY_MEAN'])
    annual_precip_dataframe['DATE'] = pandas.to_datetime(annual_precip_dataframe['DATE'], format='%Y%m%d')
    annual_precip_dataframe['YEAR'] = annual_precip_dataframe['DATE'].dt.year
    annual_precip_dataframe['WGMS_ID'] = wgms_id
    # print(annual_precip_dataframe)

    # Get annual data.
    # https://confluence.ecmwf.int/pages/viewpage.action?pageId=197702790
    # TODO: Use exact days of the month. This formula below may not be correct. verify.
    annual_precip_dataframe['TOTAL_PPT_YEAR'] = annual_precip_dataframe['PPT_MONTHLY_MEAN'] * 30
    # TODO: Units should be m/year. Is it?
    annual_ppt_final = annual_precip_dataframe.groupby(['YEAR', 'WGMS_ID'])['TOTAL_PPT_YEAR'].sum().reset_index()
    return annual_ppt_final
# ======================================================================================================================
# ======================================================================================================================


# Download precipitation data
# TODO: FIND OUT A WAY TO GET PRECIP DATA WITHOUT DOWNLOAD. MANUALLY CUOLD BE BETTER

# created outside loop to get overall data for each glacier, each year with ppt values
# data will be added to this empty inside the loop! avoid loops. There is always a way.
# TODO: Find better way.
ppt_df = pandas.DataFrame(columns=['YEAR', 'WGMS_ID', 'TOTAL_PPT_YEAR'])

for wgms_id, group in glacier_data.groupby('WGMS_ID'):
    # Get lat and lon of the glacier. Dataframe has these values in each row. Done to get a single value.
    # .iloc[0] could also work.
    lat = float(group['LATITUDE'].unique()[0])
    lon = float(group['LONGITUDE'].unique()[0])
    location = [lat, lon]

    # Same for year.
    year1 = int(group['MIN_YEAR'].unique()[0])
    year2 = int(group['MAX_YEAR'].unique()[0])

    # Download era5 for each group. This way data for all years can be downloaded in a single file.
    download_era5(location, wgms_id, year1, year2)

    # Get yearly ppt. Then add to main file.
    filename = pathlib.Path.joinpath(DOWNLOAD_FOLDER_PATH, str(wgms_id)+'_'+str(year1)+'_'+str(year2)+'.nc')
    add_df = generate_annual_data(filename, wgms_id)

    # There is some warning about something to do with na values while concatinating.
    #   'FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.
    #   In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes.
    #   To retain the old behavior, exclude the relevant entries before the concat operation.
    #   ppt_df = pandas.concat([ppt_df, add_df])'
    # TODO: Find better way. The warning is about joining empty dfs
    ppt_df = pandas.concat([ppt_df, add_df])
# ======================================================================================================================

# Get the final dataframe with ppt values for each year and wgms_id
df_final = pandas.merge(glacier_data, ppt_df, on=['YEAR', 'WGMS_ID'], how='left')

# Add other parameters to the df
df_final['BETA'] = 0.006 * (df_final['TOTAL_PPT_YEAR']) ** (1/2)
df_final['TAU'] = 13.6 * ((df_final['BETA']) ** (-1)) * ((df_final['SLOPE']) ** (-1)) * ((1 + 20 * df_final['SLOPE']) ** (-1/2)) * ((df_final['REFERENCE_LENGTH']) ** (-1/2))
df_final['C'] = 2.3 * (df_final['TOTAL_PPT_YEAR'] ** 0.6) * (df_final['SLOPE'] ** (-1))

# DATA CLEANUP FINISHED. 'df_final' has all required values.
# ======================================================================================================================
# ======================================================================================================================

# TODO: CHECK ALL FORMULAS AND UNITS. Paper suggests 'c' values between 1 and 10. Currently, 9 - 30.
#   For tau, Paper used 'Reference Length'. So single length value to use in formula?
#   Verify.
#   .
#   .

# ======================================================================================================================
# ======================================================================================================================
# print(df_final.columns)

# Actual stuff.
df_final['dL_prime'] = df_final.groupby('WGMS_ID')['L_prime'].diff()
df_final['dt'] = df_final.groupby('WGMS_ID')['YEAR'].diff()
df_final['dL_prime_dt'] = df_final['dL_prime'] / df_final['dt']
df_final['T_prime'] = (1 / df_final['C']) * df_final['L_prime'] + (df_final['TAU'] / df_final['C']) * df_final['dL_prime_dt']

# To view
for wgms_id, group in df_final.groupby('WGMS_ID'):
    group['dL_prime_dt'] = group['L_prime'].diff() / group['YEAR'].diff()
    group['T_prime'] = (1 / group['C']) * group['L_prime'] + (group['TAU'] / group['C']) * group['dL_prime_dt']
    print(group)
