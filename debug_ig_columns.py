"""
Debug IG data structure
"""
from trading_ig import IGService
from forex_config import ForexConfig

ig_service = IGService(
    username=ForexConfig.IG_USERNAME,
    password=ForexConfig.IG_PASSWORD,
    api_key=ForexConfig.IG_API_KEY,
    acc_type="DEMO",
    acc_number=ForexConfig.IG_ACC_NUMBER
)

ig_service.create_session(version="2")

response = ig_service.fetch_historical_prices_by_epic_and_num_points(
    epic="CS.D.EURUSD.TODAY.IP",
    resolution="5Min",
    numpoints=3
)

prices_df = response['prices']
print("DataFrame info:")
print(prices_df.info())
print("\nDataFrame columns:")
print(prices_df.columns)
print("\nDataFrame head:")
print(prices_df.head())
print("\nDataFrame values:")
print(prices_df)
