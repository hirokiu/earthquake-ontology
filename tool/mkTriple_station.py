# -*- coding: utf-8 -*-
from cmath import nan
import code
from email.mime import base
from fileinput import filename
import sys
import os
import csv
#from turtle import width
import pandas as pd
import re
from datetime import datetime

import requests
import json
import csv

# def load_code_mapping(csv_file):
#     """CSVから都道府県コード、市区町村コードと名称のマッピングを作成"""
#     mapping = {}
#     with open(csv_file, newline='', encoding='utf-8') as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             mapping[row["団体コード"]] = {
#                 "都道府県コード": str(row["団体コード"])[:2],
#                 "市区町村コード": row["団体コード"],
#                 "都道府県名": row["都道府県名（漢字）"],
#                 "市区町村名": row["市区町村名（漢字）"]
#             }
#     return mapping


# 1. muni.js を取得し、辞書に変換（ゼロ埋め対応）
def load_muni_mapping(url="https://maps.gsi.go.jp/js/muni.js"):
    table = str.maketrans({
        '\u3000': '',
        ' ': '',
        '\t': ''
    })
    response = requests.get(url)
    # print(response.encoding)
    response.encoding = 'utf-8'
    if response.status_code != 200:
        raise Exception("muni.js の取得に失敗しました")

    js_text = response.text

    mapping = {}
    for item in js_text.split('\n'):
        match = re.search(r"GSI.MUNI_ARRAY[^=]* = '([^']*)';", item)
        if not match:
            #raise Exception("muni.js からデータを抽出できませんでした")
            continue

        pref_code, pref_name, city_code, city_name = match.group(1).split(",")

        # ゼロ埋め処理
        city_code = city_code.zfill(5)  # 市区町村コードを5桁にする
        pref_code = pref_code[:2].zfill(2)  # 都道府県コードを2桁にする

        mapping[city_code] = {
            "都道府県コード": pref_code,
            "市区町村コード": city_code,
            "都道府県名": pref_name.translate(table),
            "市区町村名": city_name.translate(table)
        }

    return mapping

def get_japan_admin_info(lat, lon, mapping):
    """国土地理院APIを使用して、緯度経度から都道府県・市区町村情報を取得"""
    url = f"https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress?lat={lat}&lon={lon}"
    print(url)

    response = requests.get(url)
    if response.status_code != 200:
        return None

    data = response.json()
    print(data)
    # 都道府県コードと市区町村コードを取得
    city_code = data.get("results", {}).get("muniCd", "")  # 市区町村コード
    print(city_code)

    if city_code in mapping:
        return mapping[city_code]
    else:
        # return {"都道府県コード": "", "都道府県名": "不明", "市区町村名": "不明"}
        return None

# 
'''
URI	schema:spatial	skos:prefLabel	schema:address	schema:latitude	schema:longitude	schema:availabilityStarts	schema:availabilityEnds	
'''

prefix_text = """PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX schema: <http://schema.org/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX ic: <http://imi.go.jp/ns/core/rdf#>

PREFIX jpe: <https://seismic.balog.jp/ontology/jp-earthquake.ttl#>

"""


base_dir = '/Users/hiroki_u/Documents/git/earthquake-ontology' # 後で消す or .env とconfig.envの形式にする
data_dir = 'data/'
# JMA_dir = 'JMA/'
# KNET_dir = 'K-NET/'

# 全国地方公共団体コード対応表のファイル名
# csv_file = os.path.join(base_dir,data_dir,"市区町村コード対応表_000925835.csv")
# CSVデータの読み込み
# mapping = load_code_mapping(csv_file)
mapping = load_muni_mapping()

filename = 'STAs/code_p.dat'
# filename = 'sitepub_all_utf8.csv'

ttl_list = []

def convert_JMA_stationList(_filename):

    _ttl_list = []
    _ttl_list.append(prefix_text)

    with open(_filename, encoding='utf-8', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        # ヘッダ行だけを読み込んで、スペース区切りで表示
        header = next(reader)
        #print(' '.join(header))
        for cols in reader:
            #print(cols)
            _ttl = "<https://seismic.balog.jp/resource/" + cols[0] + "> a jpe:observer ;"
            _ttl += '    schema:spatial "' + cols[1] + '"@ja ;'
            _ttl += '    skos:prefLabel "' + cols[2] + '"@ja ;'
            _ttl += '    schema:address "' + cols[3] + '"@ja ;'
            _ttl += '    schema:latitude ' + cols[4] + ' ;'
            _ttl += '    schema:longitude ' + cols[5] + ' ;'
            if cols[7] :
                _ttl += '    schema:availabilityStarts "' + cols[6] + '" ;'
                _ttl += '    schema:availabilityEnds "' + cols[7] + '" .'
            else :
                _ttl += '    schema:availabilityStarts "' + cols[6] + '" .'
            _ttl += ''
        _ttl_list.append(_ttl)

    return _ttl_list

def convert_JMA_code_p(_filename):

    _ttl_list = []
    _ttl_list.append(prefix_text)

    with open(_filename, encoding='sjis', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        # ヘッダ行だけを読み込んで、スペース区切りで表示
        #header = next(reader)
        #print(' '.join(header))
        for cols in reader:
            print(cols[1])
            _ttl = "<https://seismic.balog.jp/resource/sta-jma-" + cols[0] + "> a jpe:observer ;\n"
            _ttl += '    jpe:stationIdentifier "' + cols[0] + '" ;\n'
            _ttl += '    rdfs:label "' + cols[1] + '"@ja ;\n'
            _ttl += '    skos:prefLabel "' + cols[1] + '"@ja ;\n'

            # 緯度経度の取得
            latitude = float(cols[2][0:2]) + float(cols[2][2:4])/60
            longitude = float(cols[3][0:3]) + float(cols[3][3:5])/60
            _ttl += '    schema:latitude ' + str(latitude) + ' ;\n'
            _ttl += '    schema:longitude ' + str(longitude) + ' ;\n'

            # 住所の取得
            print("住所の取得")
            result = get_japan_admin_info(latitude, longitude, mapping)
            if result:
                print("住所をturtleに変換")
                print(result)
                _ttl += '    schema:address "' + result["都道府県名"] + result["市区町村名"] + '"@ja ;\n'
                _ttl += '    ic:住所 <https://uedayou.net/loa/' + result["都道府県名"] + result["市区町村名"] + '> ;\n'
                _ttl += '    ic:都道府県 "' + result["都道府県名"] + '"@ja ;\n'
                _ttl += '    ic:都道府県コード "' + result["都道府県コード"] + '" ;\n'
                _ttl += '    ic:市区町村 "' + result["市区町村名"] + '"@ja ;\n'
                _ttl += '    ic:市区町村コード "' + result["市区町村コード"] + '" ;\n'

            _ttl += '    schema:organization "' + "気象庁(JMA)" + '"@ja ;\n'
            if cols[5] :
                _ttl += '    schema:availabilityStarts "' + cols[4] + '" ;\n'
                _ttl += '    schema:availabilityEnds "' + cols[5] + '" .\n'
            else :
                _ttl += '    schema:availabilityStarts "' + cols[4] + '" .\n'
            _ttl += '\n'

            _ttl_list.append(_ttl)

    return _ttl_list

##
#
##
# K-netとkik-net両方入ったファイル
def convert_KNET_sitepub(_filename):

    _ttl_list = []
    _ttl_list.append(prefix_text)

    with open(_filename, encoding='utf8', newline='') as f:
        reader = csv.reader(f, delimiter=',')
        # ヘッダ行だけを読み込んで、スペース区切りで表示
        #header = next(reader)
        #print(' '.join(header))
        for cols in reader:
            #print(cols)
            _ttl = "<https://seismic.balog.jp/resource/sta-K-NET-" + cols[0] + "> a jpe:observer ;"
            _ttl += '    jpe:stationIdentifier "' + cols[0] + '" ;'
            _ttl += '    jpe:sobservationNetwork "' + cols[0] + '" ;'

            _ttl += '    rdfs:label "' + cols[1] + '"@ja ;'
            _ttl += '    skos:prefLabel "' + cols[1] + '"@ja ;'
            _ttl += '    skos:altLabel "' + cols[2] + '"@en ;'
            _ttl += '    schema:latitude ' + cols[3] + ' ;'
            _ttl += '    schema:longitude ' + cols[4] + ' ;'
            _ttl += '    schema:address "' + cols[6] + '"@ja ;'
            _ttl += '    schema:organization "' + "気象庁(JMA)" + '"@ja ;'
            if cols[9] : # 運用中のデバイス
                _ttl += '    schema:observationNetwork "' + cols[9] + '" .'
            if cols[10] : # ステータスが休止かどうか
                _ttl += '    schema:availabilityEnds "' + cols[5] + '" .'
            else :
                _ttl += '    schema:availabilityStarts "' + cols[4] + '" .'
            _ttl += ''
        _ttl_list.append(_ttl)

    return _ttl_list

if __name__ == "__main__":

    _target = os.path.join(base_dir,data_dir,filename)
    ttl_list = convert_JMA_code_p(_target)

    with open('output.ttl', mode='w') as f:
        f.write('\n'.join(ttl_list))
        f.write('\n')
    print('output.ttl に出力しました。')
