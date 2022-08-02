from readline import set_completion_display_matches_hook
from sys import set_asyncgen_hooks
from telnetlib import STATUS
from django.shortcuts import render
from urllib3 import HTTPResponse
from .IBAPI.main import *
from .IBAPI.learn import *
#from .IBAPI.stream_manager import *
import datetime as dt
import pytz as pytz
import threading
import pandas as pd
import time
from pandas.tseries.holiday import USFederalHolidayCalendar as calendar
import os
import json
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy


tz = pytz.timezone('US/Eastern')

def get_status():
    with open('base/IBAPI/Data/status.txt', 'r') as status_file:
        status = status_file.read()
        status_file.close()
    if app.isConnected() and status != 'running':
        set_status("connected")    
    return status

def set_status(arg=None):
    print(f"###{app.isConnected()}###")
    if app.isConnected():
        if arg == "connected":
            with open('base/IBAPI/Data/status.txt', 'w') as status_file:
                    status_file.write('connected')
                    status_file.close()
        
        elif arg == "running":
            with open('base/IBAPI/Data/status.txt', 'w') as status_file:
                    status_file.write('running')
                    status_file.close()
    else:
        with open('base/IBAPI/Data/status.txt', 'w') as status_file:
                    status_file.write('not connected')
                    status_file.close()
    

def connect():
    app.connect(host='127.0.0.1', port=7497, clientId=23) #port 4002 for ib gateway paper trading/7497 for TWS paper trading

    if (app.isConnected()):
        set_status("connected")
        # start of the connection thread||
        con_thread = threading.Thread(target=websocket_con, args=(app,), daemon=True)
        con_thread.start()
        time.sleep(1)
    
        
def trading_bot():
    while True:
        # for ticker in tickers_chosen:
        #     # activates streamData function which activates tick by tick data wrapper function
        #     streamData(app, tickers_chosen.index(ticker), usTechStk(ticker))
        #     print(f'streaming data for {ticker}')

        # with open('base/IBAPI/Data/lasttradingday.txt', 'r') as text_file:
        #     last_trading_day = text_file.read()     
        #     text_file.close()

        if exit_event.is_set() or get_status() == "not connected":
            time.sleep(2)
            pass
        
        else:
            ## write TB here!!! ###
            print('1')
            time.sleep(2)

    now = tz.localize(dt.datetime.now())
    if now.time() > dt.time(16):
        with open('base/IBAPI/Data/lasttradingday.txt', 'w') as text_file:
            text_file.write(now.date().strftime('%Y-%m-%d'))
            text_file.close()



global bot_thread
bot_thread = threading.Thread(target=trading_bot, args=(), daemon=False)

def traidingDayCond():
        # standardize to eastern timezone to prevent issues
        tz = pytz.timezone('US/Eastern')
        now = tz.localize(dt.datetime.now())
        return now.time() >= dt.time(9,30) and now.time() < dt.time(15, 59) and now.weekday() < 5 #and now.date() not in holidays

connect()

set_status("connected")
def home(request):
    # list of all the stock names (to be displayed to front end)
    tickers_chosen = []
    context = {}

    context['stock_names'] = stock_names
    # to notify user if he has selected any stocks
    tickers_is_empty = True if len(tickers_chosen)==0 else False

    stoploss = '0%'


    # dataframe of positions handled by TradeApp object
    app.reqPositions()
    pos_df = app.pos_df
    json_pos = pos_df.reset_index().to_json(orient ='records')
    pos = []
    pos = json.loads(json_pos)
    context['pos'] = pos

    #  dataframe of account summary
    app.reqAccountSummary(1, "All", "$LEDGER:ALL")
    time.sleep(1)
    acc_summ_df = app.summary_df
    json_account = acc_summ_df.reset_index().to_json(orient ='records')
    account = []
    account = json.loads(json_account)
    
    #cash_balance = acc_summ_df.iloc[acc_summ_df['Tag']=='CashBalance']['Value']

    #acc_summ_df.to_excel('accsummary.xlsx')

    # reads the status.txt file to establish wether we are connected or running
    # this may need some improvement as we affirm "connected" regardless of the
    # true connection status

    # whenever a button is pressed (either to start or stop the bot)
    if request.method == "POST":
        #this triggers the learning algorithm
        if 'learn' in request.POST:
            learnNewModel()     # from learn.py 
        # if the trading bot is running (we will stop it)
        if get_status() == 'running':
            # change the status in status.txt from "running" to "connected"
            set_status('connected')
            
            exit_event.set()

            if 'sellall' in request.POST:
                print('-'*15)
            # this sets an event which activates the flag "exit_event"
            # this triggers an if statement in the "trading_bot" function
            # which stops the bot until the flag is deactivated

        elif get_status() == 'not connected':
            connect()
            exit_event.set()
        # if the program is connected (we will start the trading bot)
        elif get_status() == 'connected':
            # change the status in status.txt from "connected" to "running"
            set_status('running')

            # fetches the list of stock selected from the front end
            stocks = request.POST.getlist('stocks')
            context['stocks_selected'] = stocks
            # converts them into tickers_chosen (formatted for IBKR)
            tickers_chosen = [stocks_dict[name] for name in stocks]
            context['tickers'] = tickers_chosen
            # if no tickers_chosen were selected (this will throw a warning on the front-end)
            # should be changed (it makes no sense to start bot with no stocks)
            tickers_is_empty = True if len(tickers_chosen)==0 else False
            context['tickers_is_empty'] = tickers_is_empty
            # creates sql table if there are none for the specific ticker
            #managesql(tickers_chosen)

            # gets the stop loss (must be converted into a float)
            stoploss = request.POST.get('stoploss')
            context['stoploss'] = stoploss

            # either "bot_thread" was not started or a flag was set
            # this handles both exceptions
            try:
                # if the bot was never started
                bot_thread.start()
            except:
                # if the "exit_event" flag was set (this clears it)
                exit_event.clear()

    # to let the front end know wether we're "connected" or "running"
    status = get_status()
    context["status"] = status

    return render(request, 'home.html', context) 