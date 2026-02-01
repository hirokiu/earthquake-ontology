from obspy import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.geodetics.flinnengdahl import FlinnEngdahl
import sys
import time
import re
from datetime import date

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

def create_date_variables(year, _month):
    if _month > 0 :
        start_date = date(year, 12-_month, 1)
        end_date = date(year, 12-_month+1, 1)
    else :
        start_date = date(year, 12, 1)
        end_date = date(year+1, 1, 1)

    return start_date, end_date

def _create_date_variables(year, half):
    if half > 0 :
        start_date = date(year, 1, 1)
        end_date = date(year, 7, 1)
    else :
        start_date = date(year, 7, 1)
        end_date = date(year+1, 1, 1)

    return start_date, end_date

if __name__ == '__main__':
    # コマンドライン引数から年を取得
    if len(sys.argv) != 2:
        print("年を引数として指定してください。")
        sys.exit(1)

    try:
        year = int(sys.argv[1])
    except ValueError:
        print("年は整数で指定してください。")
        sys.exit(1)


    client = Client()
    fe = FlinnEngdahl()

    # PREFIXの出力
    print(prefix_text)

    # 前半と後半
    for i in range(2) :
        time.sleep(1)

        # 年の1月1日と12月31日の変数を作成
        #start_date, end_date = create_date_variables(year, i)
        start_date, end_date = _create_date_variables(year, i)

        # 結果を表示
        #print("開始日:", start_date)
        #print("終了日:", end_date)
        starttime = UTCDateTime(start_date)
        endtime = UTCDateTime(end_date)

        try :
            #starttime = UTCDateTime("2000-01-01")
            #endtime = UTCDateTime("2000-12-31")
            #cat = client.get_events(eventid="gfz2023isro")
            cat = client.get_events(starttime=starttime, endtime=endtime, minmagnitude=3)
            #print(cat)
            #print(cat.__str__(print_all=True))

            for _event in cat :
                # print(_event)
                # print(_event['resource_id'])
                # print(_event['event_type'])
                # print(_event['event_descriptions'][0])
                # print(_event['event_descriptions'][0]['text'])
                # print(_event['event_descriptions'][0]['type'])
                epicenter_name = fe.get_region(_event['origins'][0]['longitude'],_event['origins'][0]['latitude'])
                # print(_event['origins'][0])
                # print(_event['origins'][0]['time'])
                # print(_event['origins'][0]['resource_id'])
                # print(_event['origins'][0]['longitude'])
                # print(_event['origins'][0]['latitude'])
                # print(_event['origins'][0]['depth'])
                # print(_event['origins'][0]['creation_info']['author'])
                # print(_event['magnitudes'][0])
                # print(_event['magnitudes'][0]['mag'])
                # print(_event['magnitudes'][0]['magnitude_type'])
                # print(_event['magnitudes'][0]['creation_info']['author'])

                print(f"<http://{str(_event['resource_id'])[4:]}> a jpe:hypocenter ;")
                print(f"\trdfs:label \"{epicenter_name}\" ;")
                print(f"\tskos:altLabel \"{_event['event_descriptions'][0]['text']}\" ;")
                if _event['origins'][0]['creation_info'] is not None :
                    print(f"\tjpe:catalog \"{_event['origins'][0]['creation_info']['author']}\" ;")
                if _event['magnitudes'][0]['creation_info'] is not None :
                    print(f"\tjpe:determinatedWay \"{_event['magnitudes'][0]['creation_info']['author']}\" ;")
                print(f"\tjpe:originTime \"{_event['origins'][0]['time']}\" ;")
                print(f"\tschema:latitude {_event['origins'][0]['latitude']} ;")
                print(f"\tschema:longitude {_event['origins'][0]['longitude']} ;")
                if re.match(r'^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$', str(_event['origins'][0]['depth'])) :
                    print(f"\tjpe:depth {_event['origins'][0]['depth']} ;")
                print(f"\tjpe:magnitude {_event['magnitudes'][0]['mag']} ;")
                if _event['magnitudes'][0]['magnitude_type'] is not None :
                    print(f"\tjpe:magnitudeType \"{_event['magnitudes'][0]['magnitude_type']}\" .")
                else :
                    print(f"\tjpe:magnitudeType \"None\" .")
                print()
                #for _data in _event :
                #    print(f"{_data} : {_event[_data]}")

        except ValueError :
            print(f"データ処理エラー：${ValueError}")
            sys.exit(1)
