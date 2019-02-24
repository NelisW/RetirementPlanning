import os
import sys
import numpy as np
import pandas as pd
from datetime import date
from collections import OrderedDict
from dateutil.relativedelta import *
import matplotlib.pyplot as plt
from IPython.core.pylabtools import figsize


sys.path = ["./"]+sys.path

import utilityfuns as ufun
import fingenerators as fingen




# ============================================================================
def rentalProperty(principal,interest_rate,bondyears,calcyears,rentpmonth,rentpermonthInc,agentPcnt,levy,
                   ratesnt,levyInc,ratesntInc,maintPcnt,
                   taxrate,riskPcnt=0,cyclesPerAnnum=12,doplot=False,start_date=date(2000, 1,1),
                   ID=''):
    
    reqpayment = round(np.pmt(rate=interest_rate/cyclesPerAnnum, nper=bondyears*cyclesPerAnnum, 
                              pv=principal, fv=0, when='end'),2)
   
    
    df, stats = fingen.amortisation_table(
        principal=principal, 
        interest_rate=interest_rate, 
        bondyears=bondyears, 
        reqpayment = reqpayment,
        cyclesPerAnnum=cyclesPerAnnum,
        start_date=start_date,
        ID=ID,
        )
    numcycles = stats['Num Payments']
    
    # if loan is paid off before end of the term add zero-content lines
    if numcycles < calcyears * cyclesPerAnnum + 1:
        if numcycles == 0:
            df = pd.DataFrame()
            curdate = start_date
        else:
            curdate = stats['Payoff Date']
        while numcycles < calcyears * cyclesPerAnnum + 1:
            # add additional lines with zero interest costs 
            dic =  OrderedDict([('Month',curdate),
                           ('Period', numcycles+1),
                           ('Begin Balance', 0),
                           ('ReqPayment', 0),
                           ('Principal', stats['Principal']),
                           ('InterestRate', df['InterestRate'].mean()),
                           ('Interest', 0),
                           ('AddPayment', 0),
                           ('End Balance', 0),
                           ('ID',ID),
                               ],)
            df = df.append(pd.DataFrame(dic, index=[numcycles]),sort=True)
            curdate += relativedelta(months=1)
            numcycles += 1

    # rent income
    rischedule = fingen.annIncreaseTable(value=rentpmonth, increasepyear=rentpermonthInc, numcycles=numcycles)
    # costs
    levyschedule = fingen.annIncreaseTable(value=levy, increasepyear=levyInc, numcycles=numcycles,colhead='Levy')
    ratesntschedule = fingen.annIncreaseTable(value=ratesnt, increasepyear=ratesntInc, numcycles=numcycles,colhead='RatesT')


    # Now merge the bond table with the rent income table
    dfc = df.copy().drop(["AddPayment"],axis=1)
    dfc = dfc.merge(rischedule.drop(["Month"],axis=1), on='Period')
    dfc = dfc.merge(levyschedule.drop(["Month"],axis=1), on='Period')
    dfc = dfc.merge(ratesntschedule.drop(["Month"],axis=1), on='Period')

    #agent fees
    dfc['Agent'] = -agentPcnt * dfc['Rent']
    
    #maintenance
    dfc['Maint'] = -maintPcnt * dfc['Rent']

    #risk
    dfc['Risk'] = -riskPcnt * dfc['Rent']
    
    # number of payments
    dfc['NumPay'] = stats['Num Payments']

    # save tax for later
    dfc['TaxRate'] = taxrate
    
    #costs
    dfc['Costs'] = dfc['Interest']+ dfc['Agent']+ dfc['Levy']+ dfc['RatesT'] + dfc['Maint'] + dfc['Risk']
    
    # rent after cost before tax
    dfc['RentAfterCosts'] = dfc['Rent'] +   dfc['Costs']
    
    # tax and net income if bond present; can't get tax back on losses
    dfc['TaxRate'] =  taxrate 
    dfc['Tax'] = - taxrate * (dfc['RentAfterCosts'] )
    dfc['Tax'][dfc['Tax'] > 0] = 0
    
    dfc['Costs+Tax'] = dfc['Tax'] + dfc['Costs']
    dfc['Income'] = dfc['Rent'] + dfc['Costs+Tax'] 
    dfc['CashFlow'] = dfc['ReqPayment'] + dfc['Income']

    dfc['RentAfterCostsFrac'] = dfc['RentAfterCosts'] / dfc['Rent']
   
    
    #Create a summary statistics table
    istats = pd.Series([stats['Principal'],stats['Interest Rate'],stats['BondYears'],
                        stats['ReqPayment'],stats['Total Interest'],
                        dfc['CashFlow'].sum(),dfc["Period"].count(),
                        calcyears,
                         rentpmonth,  rentpermonthInc,
                         levy,  levyInc,
                         ratesnt,  ratesntInc,
                         taxrate,agentPcnt,
                         dfc['Maint'].sum(),maintPcnt,
                         dfc['Risk'].sum(),riskPcnt,
                         dfc["Rent"].sum(),
                         dfc["Tax"].sum(),
                         dfc["Income"].sum(),
                         dfc['RentAfterCosts'].sum() / dfc['Rent'].sum(),
                         ID,
                        ],
                       index=["Bond","Interest Rate","BondYears",
                              "ReqPaymentMonth","TotalInterest",
                              "CumCashFlow","Num Payments",
                              "CalcYears",
                              "InitRent",  "RentIncrease",
                              "InitLevy",  "LevyIncrease",
                              "InitR&T",  "R&TIncrease",
                              "TaxRate","AgentPcnt",
                              "Maint","MaintPcnt",
                              "Risk","RiskPcnt",
                              "Total Rent",
                              "Tax",
                              "Income",
                              "RentAfterCostsB4TaxFrac",
                              "ID",
                             ])


    if doplot:
        plotrentalpropcashflowtimeline(dfc)        
        plotrentalpropeffectiverent(dfc)        

#     display(HTML(dfc.head().to_html()))
#     display(HTML(dfc.tail().to_html()))
#     stats
    return dfc,istats


# ============================================================================
def plotrentalpropcashflowtimeline(dfc):
    import matplotlib.pyplot as plt
    figsize(12,8)
    fig, axes = plt.subplots(nrows=1, ncols=1)
    taxrate = dfc['TaxRate'].mean()
    interest_rate = dfc['InterestRate'].mean()
    ID = dfc.iloc[0]['ID']
    dfc.plot(x='Month',y='Rent', label='Gross rent income', ax=axes)    
    dfc.plot(x='Month',y='RentAfterCosts', label='Net rent income after costs before tax', ax=axes)    
    dfc.plot(x='Month',y='Interest', label=f'Interest={interest_rate:.4f}', ax=axes)    
    dfc.plot(x='Month',y='Costs+Tax', label='Costs+Tax', ax=axes)  
    dfc.plot(x='Month',y='CashFlow', label='Cash flow', ax=axes)    
    dfc.plot(x='Month',y='Tax', label=f'Tax={taxrate:.3f}', ax=axes)    
    plt.title(f"{ID} Rental property cash flow timelines");
    plt.ylabel("Value");
    plt.xlabel("Time");


# ============================================================================
def plotrentalpropeffectiverent(dfc):
    import matplotlib.pyplot as plt
    
    ID = dfc.iloc[0]['ID']
    meanval = dfc['RentAfterCosts'].sum() / dfc['Rent'].sum()
    figsize(12,8)
    fig, axes = plt.subplots(nrows=1, ncols=1)
    dfc.plot(x='Month',y='RentAfterCostsFrac', label='Rent-after-costs-before-tax / Rent', ax=axes,ylim=[0,1])    
    plt.title(f"{ID} Effective rent after cost before tax, mean value={meanval:.3f}");
    plt.ylabel("Fraction");
    plt.xlabel("Time");    