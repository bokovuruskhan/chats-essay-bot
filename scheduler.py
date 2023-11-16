import requests
from index import log
from config import SCHEDULER_INTERVAL_SECONDS
import sched, time

s = sched.scheduler(time.time, time.sleep)
url1 = "http://95.143.190.136:5000/essay"
url2 = "http://95.143.190.136:5000/subscribe/check"


def f():
    s.enter(SCHEDULER_INTERVAL_SECONDS, 1, f)
    try:
        requests.get(url1)
        requests.get(url2)
    except Exception as e:
        log(str(e), key="Scheduler /essay or /subscribe/check request")


f()
s.run()
