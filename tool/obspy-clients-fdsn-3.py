from obspy import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.clients.fdsn.header import URL_MAPPINGS
import re
import time

#for key in sorted(URL_MAPPINGS.keys()):
#    print("{0:<11} {1}".format(key,  URL_MAPPINGS[key]))  

prefix_text = """PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX schema: <http://schema.org/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX jpe: <https://seismic.balog.jp/ontology/jp-earthquake.ttl#>

"""

file_path = "./fdsn_sta_id_list.txt"  # ファイルのパスを指定
station_list = {}  # 結果を格納するリスト

with open(file_path, "r") as file:
    for line in file:
        line = line.strip()  # 行末の改行文字を削除
        # 行の処理を実行
        _matches = re.findall(r'(([a-zA-Z0-9]+)\.([a-zA-Z0-9]+) \([^\)]*\))',line)
        if _matches[0][1] not in station_list :
            station_list[_matches[0][1]] = {}
        station_list[_matches[0][1]][_matches[0][2]] = _matches[0][0]

#print("観測点リスト作成完了")
# PREFIXの出力
print(prefix_text)

client = Client()
# 結果を表示
for _nw in station_list :
    print(f"-->{_nw}")
    time.sleep(1)
    try :
        inventory = client.get_stations(network=_nw)
        network_list = inventory.networks
        for _network in network_list :
            #print(_network)
            for _station in _network.stations :
                if _station.code in station_list[_nw] :
                    print(f"<https://seismic.balog.jp/resource/sta-FDSN-{_nw}.{_station.code}> a jpe:observer ;")
                    print(f"\trdfs:labal \"{_nw}.{_station.code}\" ;")
                    print(f"\trdfs:labal \"{station_list[_nw][_station.code]}\" ;")
                    print(f"\tskos:prefLabal \"{_nw}.{_station.code}\" ;")
                    print(f"\tskos:altLabal \"{station_list[_nw][_station.code]}\" ;")
                    print(f"\tschema:latitude {_station.latitude} ;")
                    print(f"\tschema:longitude {_station.longitude} ;")
                    print(f"\tschema:elevation {_station.elevation} ;")
                    print(f"\tjpe:stationIdentifier \"{_nw}.{_station.code}\" .")
                    print()
                    #schema:availabilityStarts "199604011200" .
    except :
        pass

# for _sta in station_list[_network] :
#     print(_sta)
#     print(station_list[_network][_sta])

# starttime = UTCDateTime("2002-01-01")
# endtime = UTCDateTime("2002-01-02")
#inventory = client.get_stations()
#inventory = client.get_stations(network="IU", station="A*",
#                                starttime=starttime,
#                                endtime=endtime)
#print(inventory)
#inventory.plot()

#         cnt_sta += 1

#print(f"ネットワーク数：{cnt_nw}")
#print(f"ステーション数：{cnt_sta}")
#inventory.plot()