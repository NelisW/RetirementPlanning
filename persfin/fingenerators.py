import os
import sys
import numpy as np
import pandas as pd
from datetime import date
from collections import OrderedDict
from dateutil.relativedelta import *
import matplotlib.pyplot as plt

sys.path = ["./"]+sys.path

import utilityfuns as ufun


# ============================================================================
def amortise(principal, interest_rate, bondyears, reqpayment, addpayment,start_date, 
             cyclesPerAnnum,addpayrate=0,ID=''):
    """
    Calculate the amortization schedule given the loan details.

    :param principal: Amount borrowed
    :param interest_rate: The annual interest rate for this loan
    :param bondyears: Number of years for the loan
    :param reqpayment: Payment amount per period
    :param addpayment: Initial value of additional payments to be made each period.
    :param start_date: Start date for the loan.
    :param cyclesPerAnnum: Number of payment cycles in a year.
    :param addpayrate: Rate of increase in additional payment, calculated once per year.
    :param ID: String ID for this calculation.

    :return: 
        schedule: Amortization schedule as an Ordered Dictionary
    """

    # initialize the variables to keep track of the periods and running balances
    p = 1
    beg_balance = principal
    end_balance = principal
    currentyear = start_date.year

    while end_balance > 0:
        
        # Recalculate the interest based on the current balance
        interest = - round(((interest_rate/cyclesPerAnnum) * beg_balance), 2)
        
        # Determine payment based on whether or not this period will pay off the loan
        reqpayment = - min(-reqpayment, beg_balance - interest)
        
        # Ensure additional payment gets adjusted if the loan is being paid off
        addpayment = - min(-addpayment, beg_balance - interest + reqpayment)
        
        end_balance = beg_balance - interest  + reqpayment  + addpayment

        yield OrderedDict([('Month',start_date),
                           ('Period', p),
                           ('Begin Balance', beg_balance),
                           ('ReqPayment', reqpayment),
                           ('Principal', principal),
                           ('InterestRate', interest_rate),
                           ('Interest', interest),
                           ('AddPayment', addpayment),
                           ('End Balance', end_balance),
                           ('ID', ID),
                          ])
        
        # Increment the counter, balance and date
        p += 1
        
        if cyclesPerAnnum == 12:
            start_date += relativedelta(months=1)
        elif  cyclesPerAnnum == 365.25:
            start_date += relativedelta(days=1)
        else:
            print(f'Unknown cyclesPerAnnum = {cyclesPerAnnum}')
            return None

        beg_balance = end_balance
        
        # only increase the additional payment once per year
        if start_date.year != currentyear:
            currentyear = start_date.year
            addpayment *= 1 + addpayrate

            

# ============================================================================
def amortisation_table(principal, interest_rate, bondyears,reqpayment,
                       addpayment=0, cyclesPerAnnum=12, start_date=(date(2000,1,1)),addpayrate=0,ID=''):
    """
    Calculate the amortization schedule given the loan details as well as summary stats for the loan

    :param principal: Amount borrowed (positive)
    :param interest_rate: The *annual* interest rate for this loan (positive)
    :param bondyears: Number of years for the loan (positive)
    :param reqpayment: minimum required payment to meet the term requirements (negative)
    :param cyclesPerAnnum (optional): Number of payment cycles in a year. Default 12.
    :param addpayment (optional): Additional payments to be made each period. ** See note below. Default 0. (negative)
    :param start_date (optional): Start date. Default 2000-01-01 if none provided
    :param addpayrate: Rate of increase in additional payment, calculated once per year.

    The additional payment can be specified as a money value or as a fraction  
    of the required payment. Complex value notation is used where the money value 
    is the real component (e.g., -2300, negative value) and the fraction value is 
    the imaginary component (e.g., .02j, positive fraction). If the (negative) real component 
    (money value) is given the (positive) imaginary component (fraction value) is ignored.

    :return: 
        schedule: Amortization schedule as a pandas dataframe
        summary: Pandas dataframe that summarizes the payoff information
    """
    
    if np.real(addpayment) != 0:
        addpayment = np.real(addpayment)
    elif np.imag(addpayment) != 0:
             addpayment = reqpayment * np.imag(addpayment )
    else:
        addpayment = 0
    
    # Generate the schedule 
    schedule = pd.DataFrame(amortise(principal, interest_rate, bondyears, reqpayment,
                                     addpayment, start_date, cyclesPerAnnum,addpayrate=addpayrate,
                                    ID=ID))
    
    if schedule.empty:
        stats = pd.Series([0,start_date, 0, interest_rate,
                   0, 0, 0,0,0,ID],
                   index=["Principal","Payoff Date", "Num Payments", "Interest Rate", "BondYears", 
                         "ReqPayment", "AddPayment", "Addpayrate","Total Interest",ID])

        return None, stats

    # reorder the columns
    schedule = schedule[["Period", "Month", "Begin Balance", "ReqPayment","AddPayment",
                         "Interest", "End Balance",'Principal','InterestRate','ID']]

    # Convert to a pandas datetime object to make subsequent calcs easier
    schedule["Month"] = pd.to_datetime(schedule["Month"])
    
    #Create a summary statistics table
    payoff_date = schedule["Month"].iloc[-1]
    stats = pd.Series([principal,payoff_date, schedule["Period"].count(), interest_rate,
                       bondyears, reqpayment, addpayment,addpayrate,
                       schedule["Interest"].sum(),ID],
                       index=["Principal","Payoff Date", "Num Payments", "Interest Rate", "BondYears", 
                             "ReqPayment", "AddPayment", "Addpayrate","Total Interest","ID"])
    
    return schedule, stats



            

# ============================================================================
# to calculate the annually increased value into a DataFrame
def fixed_annualIncrease(value, increasepyear, numcycles, date, colhead='Value'):
    """Yields an OrderedDict for a value increasing at a fixed ratem
    
    Calculates the value increasing once per year (not every month) on January 01
    at the stated annual rate.
    """

    p = 1
    currentyear = date.year

    while p < numcycles + 1:      
        yield OrderedDict([('Month',date),('Period', p),(colhead, value)])  
        # Increment the counter, balance and date
        p += 1
        date += relativedelta(months=1)
        # only increase the value once per year
        if date.year != currentyear:
            currentyear = date.year
            value *= 1 + increasepyear

            
# ============================================================================
def annIncreaseTable(value, increasepyear, numcycles, start_date=date(2000,1,1),colhead='Rent'):
    """Returns a dataframe for an initial value increasing at a fixed rate for a term
    
    Calculates the value increasing once per year (not every month) on January 01
    at the stated annual rate.
    """
    
    # Generate the rent income schedule 
    rischedule = pd.DataFrame(fixed_annualIncrease(value, increasepyear, numcycles,start_date,colhead=colhead))
    
    # Convert to a pandas datetime object to make subsequent calcs easier
    rischedule["Month"] = pd.to_datetime(rischedule["Month"])

    return rischedule


# ============================================================================
def investmentgrowth(initialvalue, growthrate, termyears, addpayment=0, addpaymentrate=0, 
                     costBalPcnt=0, start_date=(date(2000,1,1)), cyclesPerAnnum=12,ID=''):
    """
    Calculate the amortization schedule given the loan details.

    :param initialvalue: Initial value paid into the investment
    :param growthrate: The annual growth rate for this investment
    :param termyears: Number of years for the investment
    :param addpayment: Additional investment amount per period
    :param addpaymentrate: growth in the additional investment compounded annually 
    :param costBalPcnt: managment cost as percentage on balance
    :param start_date: Start date for the loan.
    :param cyclesPerAnnum: Number of investment payment cycles in a year.
    :param ID: String ID for this calculation.

    :return: 
        schedule: investment schedule as an Ordered Dictionary
    """

    # initialize the variables to keep track of the periods and running balances
    p = 1
    beg_balance = initialvalue
    end_balance = initialvalue
    currentyear = start_date.year

    while p < termyears * cyclesPerAnnum:
        
        # Recalculate the growth based on the current balance
        growth = - beg_balance * growthrate / cyclesPerAnnum
        
        # cost on balance
        costBal = beg_balance * costBalPcnt / cyclesPerAnnum
        
        # total costs
        costs = costBal
        
        end_balance = beg_balance - growth + addpayment - costs

        yield OrderedDict([('Month',start_date),
                           ('Period', p),
                           ('Begin Balance', beg_balance),
                           ('InitialVal', initialvalue),
                           ('GrowthRate', growthrate),
                           ('Growth', growth),
                           ('AddPayment', addpayment),
                           ('AddPayRate', addpaymentrate),
                           ('CostBalance',costBal),
                           ('costBalPcnt',costBalPcnt),
                           ('End Balance', end_balance),
                           ('ID', ID),
                          ])
        
        # Increment the counter, balance and date
        p += 1
        if cyclesPerAnnum == 12:
            start_date += relativedelta(months=1)
        elif  cyclesPerAnnum == 365.25:
            start_date += relativedelta(days=1)
        else:
            print(f'Unknown cyclesPerAnnum = {cyclesPerAnnum}')
            return None
        beg_balance = end_balance
        
        # only increase the additional payment once per year
        if start_date.year != currentyear:
            currentyear = start_date.year
            addpayment *= 1 + addpaymentrate

            
# ============================================================================
def investment_table(initialvalue, growthrate, termyears, addpayment=0, addpaymentrate=0, costBalPcnt=0,
                     start_date=(date(2000,1,1)), cyclesPerAnnum=12,ID=''):
    """
    Calculate the amortization schedule given the loan details as well as summary stats for the loan

    :param initialvalue: Initial value paid into the investment
    :param growthrate: The annual growth rate for this investment
    :param termyears: Number of years for the investment
    :param addpayment: Additional investment amount per period
    :param addpaymentrate: growth in the additional investment compounded annually 
    :param costBalPcnt: managment cost as percentage on balance
    :param start_date: Start date for the loan.
    :param cyclesPerAnnum: Number of investment payments in a year.
    :param ID: String ID for this calculation.

    :return: 
        schedule: investment schedule as a pandas dataframe
        summary: Pandas dataframe that summarizes the investment
    """
    
    # Generate the schedule 
    schedule = pd.DataFrame(investmentgrowth(initialvalue=initialvalue, growthrate=growthrate, 
                                termyears=termyears,addpayment=addpayment, addpaymentrate=addpaymentrate, 
                                             costBalPcnt=costBalPcnt,start_date=start_date, 
                                             cyclesPerAnnum=cyclesPerAnnum,ID=ID))
    
    # reorder the columns
    schedule = schedule[['Period','Month','Begin Balance','InitialVal','GrowthRate','Growth',
                         'costBalPcnt','CostBalance','AddPayment','AddPayRate','End Balance','ID']]

    # Convert to a pandas datetime object to make subsequent calcs easier
    schedule["Month"] = pd.to_datetime(schedule["Month"])
    schedule["NettGrowth"] = schedule["End Balance"] - schedule["Begin Balance"][0]
    
    #Create a summary statistics table
    endBalance = schedule.iloc[-1]["End Balance"]
    NettGrowth = schedule.iloc[-1]["NettGrowth"]
    stats = pd.Series([ID,initialvalue,growthrate,
                       termyears,addpayment,addpaymentrate,
                       endBalance,costBalPcnt,NettGrowth],
                       index=['ID','InitialVal','GrowthRate',
                              'Years','AddPayment','AddPayRate',
                              'EndBalance','CostBalPcnt',"NettGrowth"])
    
    return schedule, stats