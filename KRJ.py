#!/usr/bin/python3
from PIL import Image, ImageOps
from PIL import ImageFont
from PIL import ImageDraw
import argparse
import qrcode
import currency
import os
import sys
import logging
from IT8951 import constants
import time
import requests
import urllib, json
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import yaml 
import socket
import subprocess
picdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'images')
fontdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fonts')
configfile = os.path.join(os.path.dirname(os.path.realpath(__file__)),'config.yaml')
fonthiddenprice = ImageFont.truetype(os.path.join(fontdir,'googlefonts/Roboto-Medium.ttf'), 30)
font = ImageFont.truetype(os.path.join(fontdir,'googlefonts/Forum-Regular.ttf'), 80)
fontHorizontal = ImageFont.truetype(os.path.join(fontdir,'googlefonts/Roboto-Medium.ttf'), 50)
font_date = ImageFont.truetype(os.path.join(fontdir,'PixelSplitter-Bold.ttf'),11)

def parse_args():
    p = argparse.ArgumentParser(description='Test EPD functionality')
    p.add_argument('-v', '--virtual', action='store_true',
                   help='display using a Tkinter window instead of the '
                        'actual e-paper device (for testing without a '
                        'physical device)')
    p.add_argument('-r', '--rotate', default=None, choices=['CW', 'CCW', 'flip'],
                   help='run the tests with the display rotated by the specified value')
    p.add_argument('-d', '--demo', action='store_true',
                   help='do a demo run-through of tools')
    return p.parse_args()

def displayqr(config, image):
    macaroon=config['lightning']['macaroon']
    tokenfilename = os.path.join(picdir,"bitcoin-lightning-accepted.png")
    tokenimage = Image.open(tokenfilename)
    amount="0"
    print(macaroon)
    openinvoice=False
    headers = {"Grpc-Metadata-macaroon" : macaroon}

    response = requests.get('https://umbrel.local:8080/v1/invoices', headers=headers, verify=False).json()
    print(response)
    lastinvoice=len(response['invoices'])-1
    image.paste(tokenimage, (100,100))
    if response['invoices'][lastinvoice]['state']=="OPEN":
        openinvoice=True
        #There is an unpaid, valid invoice
        requeststring=response['invoices'][lastinvoice]['payment_request']
        qr = qrcode.QRCode(version=1,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=1,)
        qr.add_data(requeststring)
        qr.make(fit=True)
        theqr = qr.make_image(fill_color="#000000", back_color="#FFFFFF")
        amount=response['invoices'][lastinvoice]['value']
        amountstring = format(int(amount),",")
        memo=response['invoices'][lastinvoice]['memo']
        print("AMOUNT="+amount)

        draw = ImageDraw.Draw(image)
        draw.text((550,700),"Item: "+memo,font =font,fill = 0)
        draw.text((550,840),"Scan to pay:",font =font,fill = 0)
        draw.text((550,920),amountstring+" Sats",font =font,fill = 0)
    if openinvoice==True:
        MAX_SIZE=(300,300)
        theqr.thumbnail(MAX_SIZE)
#    ImageOps.invert(theqr)
        image.paste(theqr, (130,700))
    image = ImageOps.mirror(image)
    image = ImageOps.invert(image)
    return openinvoice, image

def pollpayment(config):
    print("Paid Yet?\n\n")
    macaroon=config['lightning']['macaroon']
    headers = {"Grpc-Metadata-macaroon" : macaroon}
    response = requests.get('https://umbrel.local:8080/v1/invoices', headers=headers, verify=False).json()
    lastinvoice=len(response['invoices'])-1
    openinvoice=response['invoices'][lastinvoice]['state']  
    if openinvoice == "OPEN":
        openinvoicebool=True
    else:
        openinvoicebool=False
    print("Invoice: "+ openinvoice)
    return openinvoicebool

def display_image_8bpp(display, img):

    dims = (display.width, display.height)
    img.thumbnail(dims)
    paste_coords = [dims[i] - img.size[i] for i in (0,1)]  # align image with bottom of display
    img=img.rotate(180, expand=True)
    display.frame_buf.paste(img, paste_coords)
    display.draw_full(constants.DisplayModes.GC16)

def main():
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG)
    if not args.virtual:
        from IT8951.display import AutoEPDDisplay

        print('Initializing EPD...')

        # here, spi_hz controls the rate of data transfer to the device, so a higher
        # value means faster display refreshes. the documentation for the IT8951 device
        # says the max is 24 MHz (24000000), but my device seems to still work as high as
        # 80 MHz (80000000)
        display = AutoEPDDisplay(vcom=-2.61, rotate=args.rotate, spi_hz=80000000)

        print('VCOM set to', display.epd.get_vcom())

    else:
        from IT8951.display import VirtualEPDDisplay
        display = VirtualEPDDisplay(dims=(800, 600), rotate=args.rotate)

    try:
#       Get the configuration from config.yaml
        with open(configfile) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)



#       Note that there has been no data pull yet
        invoicechange=False
        firstrun=True
#       Time of start
        lastscreenupdate = time.time()
     
        while True:
            img = Image.new("RGB", (1448, 1072), color = (255, 255, 255) )
            if (invoicechange==True) or (firstrun==True):
                firstrun=False
                wasthereaninvoice, image=displayqr(config,img)
                lastscreenupdate = time.time()
                display_image_8bpp(display,img)
                time.sleep(2)
                isthereaninvoice=wasthereaninvoice
            else:
                isthereaninvoice=pollpayment(config)
            if isthereaninvoice != wasthereaninvoice:
                print("is:"+str(isthereaninvoice))
                print("was:"+str(wasthereaninvoice))
                invoicechange = True
                # Insert code to be triggered by this change
            else:
                print("NOCHANGE")
                invoicechange = False
            time.sleep(1)   

    except IOError as e:
        logging.info(e)
    
    except KeyboardInterrupt:    
        logging.info("ctrl + c:")
        exit()

if __name__ == '__main__':
    main()
