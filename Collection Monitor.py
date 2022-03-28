# Developed by: Aussie Degen #1251
# Last Updated: 16/03/2022



import json, time, re, os, sys
import random, threading, requests, datetime

from classes.proxymanager import ProxyManager
from classes.discord_hooks import Webhook
from classes.logger import logger

from classes import discord_hooks
from traceback import print_exc
from bs4 import BeautifulSoup
from threading import Thread
from random import uniform
from colorama import init
from os import listdir
from json import load

log = logger().log
init()

sys.setrecursionlimit(1000)

with open('config.json', 'r') as f:
    config = json.loads(f.read())
f.close()

with open('webhooks.json', 'r') as f:
    webhooks = json.loads(f.read())
f.close()


collection_monitor  = config['collection_monitor']
watch_list          = config['watch_list']
discord_id          = config['discord_id']  # For mentions in discord

listings_webhook    = webhooks['listings_webhooks']
sales_webhook       = webhooks['sales_webhooks']


# ==========================================================================================================================================================#
# ==========================================================================================================================================================#
# ==========================================================================================================================================================#
# ==========================================================================================================================================================#

class montior(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    # =========================================================================================================================================#

    def check_activity(self):

        while True:
            try:
                # Loop though collections in config file
                for collection in watch_list:

                    # Defines keywords for each collection
                    keywords = collection['keywords']

                    # Set session and add proxy
                    s = requests.session()
                    s.proxies = ProxyManager().get_next_proxy(True)

                    # Send request to get all recent activity for a certin collection
                    r = s.get("https://api-mainnet.magiceden.dev/v2/collections/{}/activities".format(collection['name']))
                    if r.status_code == 200:
                        soup = json.loads(r.text)

                        # Loop though transactions, check it is not in database file
                        for transaction in soup:
                            if transaction['signature'] not in open("dataBase.txt").read():
                                self.activity_type = transaction['type']

                                #  Filter to only scrape sold and new listings
                                if self.activity_type in ['buyNow','list']:

                                    # Send request to get NFT details
                                    r = s.get("https://api-mainnet.magiceden.dev/v2/tokens/{}".format(transaction['tokenMint']))
                                    if r.status_code == 200:
                                        token = json.loads(r.text)

                                        # Send request to get NFT collection stats
                                        r = s.get("https://api-mainnet.magiceden.dev/v2/collections/{}/stats".format(collection['name']))
                                        if r.status_code == 200:
                                            stats = json.loads(r.text)

                                            # Collect all the data for the webhook
                                            self.name           = token['name']
                                            self.image          = token['image']
                                            self.price          = transaction['price']
                                            self.floorPrice     = round(stats['floorPrice']*10**(-9), 3)
                                            self.listedCount    = stats['listedCount']
                                            self.volumeAll      = round(stats['volumeAll']*10**(-9), 3)
                                            self.me_link        = 'https://www.magiceden.io/item-details/{}'.format(transaction['tokenMint'])
                                            self.collection     = collection['name']
                                            self.attributes     = []

                                            # Account for sales / listing webhooks
                                            try:
                                                self.buyer = transaction['buyer']
                                            except:
                                                pass
                                            try:
                                                self.seller = transaction['seller']
                                            except:
                                                pass

                                            # Scrapes attributes if available
                                            try:
                                                for attribute in token['attributes']:
                                                    self.attributes.append(attribute['trait_type'] + ': ' + attribute['value'].replace('_', ' '))
                                            except:
                                                self.attributes = []

                                            # Logic to only check listing
                                            if self.activity_type == 'list':
                                                self.alert = False

                                                # Checks if price under the target buy price else check if attribute is within target price
                                                if self.price < collection['target_price']:
                                                    self.alert = True
                                                else:
                                                    for word in collection['keywords']:
                                                        if word['attribute'].upper() in str(self.attributes).upper():
                                                            if self.price < word['target_price']:
                                                                self.alert = True

                                            # Saves to database and logs in console
                                            log("NEW TRANSACTION {}".format(transaction['signature']), "success", 'dataBase.txt')

                                            # Send discord alert
                                            self.discord_alert()

                                        # ⬇ ---- Status code Error Handling ----- ⬇
                                        elif r.status_code in [401, 429, 404, 403]:
                                            log("[{}]  ERROR: PROXY {}".format(r.status_code), "error")

                                    # ⬇ ---- Status code Error Handling ----- ⬇
                                    elif r.status_code in [401, 429, 404, 403]:
                                        log( "[{}]  ERROR: PROXY {}".format(r.status_code), "error")

                    # ⬇ ---- Status code Error Handling ----- ⬇
                    elif r.status_code in [401, 429, 404, 403]:
                        log("[{}]  ERROR: PROXY {}".format(r.status_code), "error")

            # ⬇ ---- Request Error Handling ----- ⬇
            except requests.exceptions.Timeout:
                log("TIME OUT ERROR", "error")
            except requests.exceptions.ConnectionError:
                log("CONNECTION ERROR", "error")
            # ⬇ ---- Any Other Error Handling ----- ⬇
            except Exception as error:
                log("ERROR {}".format(error), "error")
                print_exc()

            time.sleep(1)

    # =========================================================================================================================================#

    def discord_alert(self):

        # Filters Sold / Listing, Add webhooks and first field
        if self.activity_type == 'buyNow':
            # Choose random webhook to avoid discord rate limiting
            embed = Webhook(random.choice(sales_webhook), color=29372)
            embed.set_title(title='{} Just Sold!'.format(self.name), url=self.me_link)
            embed.add_field(name='Sold for', value='{} Sol'.format(self.price))
        else:
            # If alert is triggered add discord ID to webhook to mention user
            if self.alert == True:
                embed = Webhook(random.choice(listings_webhook), color=29372, msg="<@{}> :money_with_wings: ".format(discord_id))
            else:
                embed = Webhook(random.choice(listings_webhook), color=29372)
            embed.set_title(title='{} Just Listed!'.format(self.name), url=self.me_link)
            embed.add_field(name='Price', value='{} Sol'.format(self.price))

        # Add webhook feilds
        embed.add_field(name='Floor', value='{} Sol'.format(str(self.floorPrice)))
        embed.add_field(name=" ﾠ", value=' ﾠ')
        embed.add_field(name='Listed', value=self.listedCount)
        embed.add_field(name='Total Volume', value='{} Sol'.format(str(self.volumeAll)))
        embed.add_field(name=" ﾠ", value=' ﾠ')

        # Adds webhook field only if nft has attributes
        if self.attributes != []:
            embed.add_field(name='Attributes', value='\n'.join(self.attributes))

        # Logic for listing / sold
        if self.activity_type == 'buyNow':
            embed.add_field(name='Buyer', value=self.buyer, inline=False)
        else:
            embed.add_field(name='Seller', value=self.seller, inline=False)

        # Add field for quick links
        embed.add_field(name=' ﾠ', value='['+'MagicEden '+']('+'https://www.magiceden.io/marketplace/{}'.format(self.collection)+')' + ' - ' + '['+'Charts '+']('+'https://www.solsniper.xyz/collection/{}'.format(self.collection)+')' + ' - ' + '['+'Moon Rank '+']('+'https://moonrank.app/collection/{}'.format(self.collection)+')', inline=False)

        # Add image as thumbnail
        embed.set_thumbnail(self.image)

        # Let everyone know I coded this shiz
        embed.set_footer(text='Created by Aussie Degen #1251', ts=True)

        # Post webhook
        embed.post()

    # =========================================================================================================================================#


    def run(self):
        self.check_activity()

# ==========================================================================================================================================================#
# ----------------------------------------------------------------------------------------------------------------------------------------------------------#
# ==========================================================================================================================================================#


if __name__ == '__main__':
    log("Starting NFT Monitor - Developed by Aussie Degen #1251", "success")

    # If module turned on start
    if collection_monitor == True:
        t = montior()
        t.start()





