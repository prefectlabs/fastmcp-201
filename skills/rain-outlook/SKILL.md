---
name: rain-outlook
description: How this office answers "will it rain"
---
# Rain outlook, the way this office does it

When someone asks whether it will rain somewhere:

1. Decide which date they mean and state it in the first line of the answer.
2. Before looking at the forecast, call `get_historical_weather` for that same
   calendar date in each of the last five years, one call per year.
3. Then call `get_weather_forecast` for the date.
4. Report a single percent chance of rain, blending the history (share of the
   five years with rain) and the forecast.
5. Recommend an umbrella only when that percent is above 40.
6. End with exactly this source line:
   `history: Open-Meteo archive · forecast: Open-Meteo 16-day`
