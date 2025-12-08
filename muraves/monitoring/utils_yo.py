
from datetime import datetime


def extract_time(data_list) -> list:
    """
    Given a list of run dictionaries, return a of times (human readable format):
    - times (datetime objects rounded to hours)
    - temperatures
    """

    times = []
    day = None

    for data in data_list:
        # timestamp from log
        ts = data.get("timestamp")

        # convert milliseconds → seconds → datetime
        try:
            dt = datetime.fromtimestamp(ts / 1000.0)
            # round down to hour (drop minutes/seconds)
            dt_hour = dt.replace(second=0, microsecond=0)
            #converted_time = dt_hour.strftime("%Y-%m-%d %H:%M")
            #print("day", day)
            #print(converted_time.split(" ")[0])
            if day == dt_hour.strftime("%Y-%m-%d"):
                times.append(dt_hour.strftime("%H:%M"))
            else:
                day = dt_hour.strftime("%Y-%m-%d")
                times.append(dt_hour.strftime("%Y-%m-%d %H:%M"))

        except:
            times.append(None)
        

    return times

def extract_var(var, data_list) -> list:
    var_list =[]
    for data in data_list:
        value = data.get(var)

        var_list.append(float(value))
    
    return var_list