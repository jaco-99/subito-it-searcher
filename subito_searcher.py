#!/usr/bin/env python3.7

from bs4 import BeautifulSoup
import json
import os
from curl_cffi import requests
from datetime import datetime

queries = dict()
apiCredentials = dict()
ntfyConfig = dict()
ntfyConfigFile = "ntfy_config"
dbFile = "searches.tracked"
telegramApiFile = "telegram_api_credentials"

log_messages = []

def get_logs():
    return log_messages

def add_log(text):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_messages.insert(0, f"[{timestamp}] {text}")
    if len(log_messages) > 50: # only last 50 logs
        log_messages.pop()

# load from file
def load_queries():
    '''A function to load the queries from the json file'''
    global queries
    global dbFile
    if not os.path.isfile(dbFile):
        return

    with open(dbFile) as file:
        queries = json.load(file)

def load_api_credentials():
    '''A function to load the telegram api credentials from the json file'''
    global apiCredentials
    global telegramApiFile
    if not os.path.isfile(telegramApiFile):
        return

    with open(telegramApiFile) as file:
        apiCredentials = json.load(file)

def print_queries():
    '''A function to print the queries'''
    global queries

    for search in queries.items():
        print("\nsearch: ", search[0])
        for query_url in search[1]:
            print("query url:", query_url)
            for url in search[1].items():
                for minP in url[1].items():
                    for maxP in minP[1].items():
                        for result in maxP[1].items():
                            print("\n", result[1].get('title'), ":", result[1].get('price'), "-->", result[1].get('location'))
                            print(" ", result[0])

def refresh(notify=False):
    '''A function to refresh the queries

    Arguments
    ---------
    notify: bool
        whether to send notifications or not

    Example usage
    -------------
    >>> refresh(True)   # Refresh queries and send notifications
    >>> refresh(False)  # Refresh queries and don't send notifications
    '''
    global queries
    try:
        for search in queries.items():
            for url in search[1].items():
                for minP in url[1].items():
                    for maxP in minP[1].items():
                        run_query(url[0], search[0], notify, minP[0], maxP[0])
    except requests.exceptions.ConnectionError:
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " ***Connection error***")
    except requests.exceptions.Timeout:
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " ***Server timeout error***")
    except requests.exceptions.HTTPError:
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " ***HTTP error***")
    except Exception as e:
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " " + e)

    add_log("Check completed")
    return get_logs()


def delete(toDelete):
    '''A function to delete a query

    Arguments
    ---------
    toDelete: str
        the query to delete

    Example usage
    -------------
    >>> delete("query")
    '''
    global queries
    queries.pop(toDelete)

def add(url, name, minPrice, maxPrice):
    ''' A function to add a new query

    Arguments
    ---------
    url: str
        the url to run the query on
    name: str
        the name of the query
    minPrice: str
        the minimum price to search for
    maxPrice: str
        the maximum price to search for

    Example usage
    -------------
    >>> add("https://www.subito.it/annunci-italia/vendita/usato/?q=auto", "auto", 100, "null")
    '''
    global queries

    # If the query has already been added previously, delete it
    if queries.get(name):
        delete(name)

    queries[name] = {url:{minPrice: {maxPrice:{}}}}


def run_query(url, name, notify, minPrice, maxPrice):
    '''A function to run a query

    Arguments
    ---------
    url: str
        the url to run the query on
    name: str
        the name of the query
    notify: bool
        whether to send notifications or not
    minPrice: str
        the minimum price to search for
    maxPrice: str
        the maximum price to search for

    Example usage
    -------------
    >>> run_query("https://www.subito.it/annunci-italia/vendita/usato/?q=auto", "query", True, 100, "null")
    '''
    products_deleted = False

    global queries
    try:
        page = requests.get(url, impersonate="chrome120", timeout=30)
    except Exception as e:
        add_log(f"Request error: {e}")
        return

    soup = BeautifulSoup(page.text, 'html.parser')

    script_tag = soup.find('script', id='__NEXT_DATA__')
    if not script_tag:
        add_log("Error: Could not find JSON data on page (Next.js data not found).")
        return

    json_data = json.loads(script_tag.string)

    try:
        items_list = json_data['props']['pageProps']['initialState']['items']['list']
    except KeyError:
        items_list = []

    msg = []

    for item_wrapper in items_list:
        product = item_wrapper.get('item')

        if not product:
            continue

        try:
            item_key = product.get('urn')
            if not item_key: continue

            title = product.get('subject', 'No Title')
            link = product.get('urls', {}).get('default', '')
            location = product.get('geo', {}).get('town', {}).get('value', 'Unknown town') + " (" + product.get('geo', {}).get('city', {}).get('shortName', 'Unknown province') + ")"

            # Price extraction
            raw_price = None
            price = "Unknown price"
            features = product.get('features', {})
            price_feature = features.get('/price')
            if price_feature and 'values' in price_feature:
                raw_price = price_feature['values'][0].get('key')

            if raw_price:
                try:
                    price = int(raw_price)
                except ValueError:
                    pass

            # Shipping extraction
            shipping = None
            features = product.get('features', {})
            shipping_feature = features.get('/item_shippable')
            raw_shipping = shipping_feature['values'][0].get('value')

            if raw_shipping:
                try:
                    shipping = "(Shipping available)"
                except ValueError:
                    pass

            is_sold = product.get('sold', False)

        except Exception as e:
            continue

        # check if the product has already been sold
        if is_sold:
            # if the product has previously been saved remove it from the file
            if queries.get(name).get(url).get(minPrice).get(maxPrice).get(link):
                del queries[name][url][minPrice][maxPrice][link]
                products_deleted = True
            continue

        if minPrice == "null" or price == "Unknown price" or price>=int(minPrice):
            if maxPrice == "null" or price == "Unknown price" or price<=int(maxPrice):
                if not queries.get(name).get(url).get(minPrice).get(maxPrice).get(link):   # found a new element
                    tmp = (
                        datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + "\n"
                        + "*" + title + "*" + "\n"
                        + "€ " + str(price) + " " + shipping + "\n"
                        + location + "\n"
                        + link + '\n'
                    )
                    msg.append(tmp)
                    queries[name][url][minPrice][maxPrice][link] ={'title': title, 'price': price, 'location': location}
                    # print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " Adding result:", title, "-", price, "-", location)

    if len(msg) > 0:
        if notify:
            if is_telegram_active():
                send_telegram_messages(msg)
            add_log("\n".join(msg))
            add_log('\n{} new elements have been found.'.format(len(msg)))
        save_queries()
    else:
        add_log('All lists are already up to date.')

        # if at least one search was deleted, update the search file
        if products_deleted:
            save_queries()

def save_queries():
    '''A function to save the queries
    '''
    with open(dbFile, 'w') as file:
        file.write(json.dumps(queries))

def save_api_credentials():
    '''A function to save the telegram api credentials into the telegramApiFile'''
    with open(telegramApiFile, 'w') as file:
        file.write(json.dumps(apiCredentials))

def is_telegram_active():
    '''A function to check if telegram is active, i.e. if the api credentials are present

    Returns
    -------
    bool
        True if telegram is active, False otherwise
    '''
    return "chatid" in apiCredentials and "token" in apiCredentials

def send_telegram_messages(messages):
    '''A function to send messages to telegram

    Arguments
    ---------
    messages: list
        the list of messages to send

    Example usage
    -------------
    >>> send_telegram_messages(["message1", "message2"])
    '''
    for msg in messages:
        request_url = "https://api.telegram.org/bot" + apiCredentials["token"] + "/sendMessage?chat_id=" + apiCredentials["chatid"] + "&parse_mode=markdown" + "&text=" + msg
        requests.get(request_url)

def in_between(now, start, end):
    '''A function to check if a time is in between two other times

    Arguments
    ---------
    now: datetime
        the time to check
    start: datetime
        the start time
    end: datetime
        the end time

    Example usage
    -------------
    >>> in_between(datetime.now(), datetime(2021, 5, 20, 0, 0, 0), datetime(2021, 5, 20, 23, 59, 59))
    '''
    if start < end:
        return start <= now < end
    elif start == end:
        return True
    else: # over midnight e.g., 23:30-04:15
        return start <= now or now < end

if os.path.isfile(dbFile):
    load_queries()
else:
    queries = {}

if os.path.isfile(telegramApiFile):
    load_api_credentials()