import numpy as np
import pandas as pd
from datetime import date
from collections import OrderedDict
from dateutil.relativedelta import *
import matplotlib.pyplot as plt



def convertcompounded(n,m,imc,returnstr=False):
    inc = n * ( (1 + imc/m) ** (m/n) -1 )
    if returnstr:
        inc = f'Effective x{n} rate of {imc} compounded x{m} is {inc}'
    return inc    


