# -*- coding: utf-8 -*-
from cmath import nan
import code
from email.mime import base
from fileinput import filename
import sys
import os
import csv
from turtle import width
import pandas as pd
import re
from datetime import datetime

'''
URI	schema:spatial	skos:prefLabel	schema:address	schema:latitude	schema:longitude	schema:availabilityStarts	schema:availabilityEnds	
'''

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

# 最大震度
max_coefficient_text = {
                    "1":"震度1",
                    "2":"震度2",
                    "3":"震度3",
                    "4":"震度4",
                    "5":"震度5(1996年9月まで)",
                    "6":"震度6(1996年9月まで)",
                    "7":"震度7",
                    "A":"震度5弱",
                    "B":"震度5強",
                    "C":"震度6弱",
                    "D":"震度6強",
                    "L":"局発地震(最大有感距離が100km未満)(1977年まで)",
                    "S":"小局発地震(最大有感距離が100km以上200km未満)(1977年まで)",
                    "M":"やや顕著地震(最大有感距離が200km以上300km未満)(1977年まで)",
                    "R":"顕著地震(最大有感距離が300km以上)(1977年まで)",
                    "F":"有感地震(1984年まで)",
                    "X":"付近有感(1996年9月まで)"
}

# 使用走時表
travel_time_table = [
    "他機関",
    "標準走時表(83Aなど)",
    "三陸沖用走時表",
    "北海道東方沖用走時表",
    "千島列島付近用走時表(1を併用)",
    "標準走時表(JMA2001)",
    "千島列島付近用走時表(5を併用)"
]

# 震源種別
hypocenter_kinds_text = {
                    "A":"震源レコード",
                    "B":"群発地震時の震源レコード",
                    "D":"震源が離れた地震の組の震源レコード",
                    "J":"気象庁による震源",
                    "U":"USGSが決定した震源",
                    "I":"その他の国際機関(ISC,IASPEIなど)による震源"
}

# 震源決定フラグ
determinated_way_text = {
                    "K":"気象庁震源",
                    "S":"気象庁参考震源",
                    "k":"簡易気象庁震源",
                    "s":"簡易参考震源",
                    "A":"自動気象庁震源",
                    "a":"自動参考震源",
                    "N":"震源固定・震源不定・未計算",
                    "F":"遠地",
                    "U":"USGS震源",
                    "I":"ISC震源",
                    "H":"震度観測時刻が時間単位までのデータ",
                    "D":"震度観測時刻が日単位までのデータ",
                    "M":"震度観測時刻が月単位までのデータ"
}


base_dir = '/Users/hiroki_u/Documents/git/earthquake-ontology' # 後で消す or .env とconfig.envの形式にする
data_dir = 'data'
shindo_dir = 'JMA/地震月報_震度'
#filename = 'i2019.dat'

#filename = 'jma-earthquake-named.tsv'
#filename = 'jma-observers.tsv'
#filename = 'JMA/地震月報_震度/code_p.dat'
#filename = 'JMA/地震月報_震度/i2019.dat'
#filename = 'JMA/地震月報_震源/h2019'

#filename = 'JMA/地震月報_震度/test_i2019.dat'

fixed_hypo_width = (1, 4, 2, 2, 2, 2, 4, 4, 3, 4, 4, 4, 4, 4, 5, 3, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 3, 24, 3, 1)

fixed_i_hypo_width = (1, 4, 2, 2, 2, 2, 4, 4, 3, 4, 4, 4, 4, 4, 5, 3, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 3, 28, 0, 0, 0, 0)
fixed_i_hypo_names = ['recode','year','month','day','hour','minute','second','time_SE','latitude_deg','latitude_min','lat_SD','longitude_deg','longitude_min','lon_SD','depth','dep_SD','mag1_1', 'mag1_2','mag1_type','mag2','mag2_type','travel_time','hypo_judge','hypo_type','max_coefficient','scale_victim','tsunami_victim','region_main','region_sub','hypo_locale','obs_number','determination_way', 'id', 'datetime']
fixed_i_obs_width = (7, 1, 2, 2, 2, 3, 1, 1, 1, 2, 1, 2, 3, 1, 5, 1, 1, 5, 1, 1, 5, 1, 1, 5, 1, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 10, 1, 5, 0, 0)
fixed_i_obs_names = ['obs_id', 'null_01', 'day', 'hour', 'minute', 'second', 'null_02', 'max_coefficient', 'null_03', 'calcShindo', 'null_04', 'max_acc_minute', 'max_acc_second', 'null_05', 'max_acc_syn', 'null_06', 'next_n', "max_acc_ns", 'null_07', 'next_e', 'max_acc_ew', 'null_08', 'next_z', 'max_acc_ud', 'null_09', 'next_FP_01', 'acc_period_ns', 'next_FP_02', 'domnant_period_ns', 'next_FP_03', 'acc_period_ew', 'next_FP_04', 'dominat_period_ew', 'next_FP_05', 'acc_period_ud', 'next_FP_06', 'dominant_period_ud', 'null_10', 'recode', 'obsed_num', 'hypo_id', 'startTime']

def read_fixed_hypo(hypo):
    # 固定長に分割する
    colspecs = [(0,17),(0,1),(1,17),(1,5),(5,7),(7,9),(9,11),(11,13),(13,17),(17,21),(21,24),(24,28),(28,32),(32,36),(36,40),(40,44),(44,49),(49,52),(52,53),(53,54),(54,55),(55,57),(57,58),(58,59),(59,60),(60,61),(61,62),(62,63),(63,64),(64,65),(65,68),(68,92),(92,95),(95,96)]
    names = ['id','recode','datetime', 'year','month','day','hour','minute','second','time_SE','latitude_deg','latitude_min','lat_SD','longitude_deg','longitude_min','lon_SD','depth','dep_SD','mag1_1', 'mag1_2','mag1_type','mag2','mag2_type','travel_time','hypo_judge','hypo_type','max_coefficient','scale_victim','tsunami_victim','region_main','region_sub','hypo_locale','obs_number','determination_way']
    df = pd.read_fwf(hypo, colspecs=colspecs, names=names)
    return df

def convert(input):
    if input.latitude_deg.dtypes == 'O' :
        input['latitude_deg'] = input['latitude_deg'].str.replace(' ', '')
    if input.longitude_deg.dtypes == 'O' :
        input['longitude_deg'] = input['longitude_deg'].str.replace(' ', '')
    if input.depth.dtypes == 'O' :
        input['depth'] = input['depth'].str.replace(' ', '')
    if input.hypo_judge.dtypes == 'O' :
        input.replace({'hypo_judge' : {'M' : 10}}, inplace=True)
        input.replace({'hypo_judge' : {' ' : nan}}, inplace=True)
    input.hypo_judge = input.hypo_judge.astype("float64")
    input.latitude_deg = input.latitude_deg.astype("float64")
    input.latitude_min = input.latitude_min.astype("float64")
    input.longitude_deg = input.longitude_deg.astype("float64")
    input.longitude_min = input.longitude_min.astype("float64")
    input.depth = input.depth.astype("float64")
    return input

def degree(input) :
    # 度分秒を度のみに直す
    # 震源固定の場合は小数点以下空白
    # 震源固定は震源評価9番。
    input.latitude_deg.mask(input.hypo_judge == 9, input.latitude_deg + (input.latitude_min / 60.0), inplace=True)
    input.longitude_deg.mask(input.hypo_judge == 9, input.longitude_deg + (input.longitude_min / 60.0), inplace=True)
    ## それ以外はF4.2なので、
    input.latitude_deg.where(input.hypo_judge == 9, input.latitude_deg + (input.latitude_min / 60.0 * 0.01), inplace=True)
    input.longitude_deg.where(input.hypo_judge == 9, input.longitude_deg + (input.longitude_min / 60.0 * 0.01), inplace=True)
    return input

def magnitude(input) :
    # マグニチュードを直す
    # 0未満の場合は以下のように表記する
    # -0.1: -1   -0.9: -9   -1.0: A0
    # -1.9: A9   -2.0: B0   -3.0: C0
    if input.mag1_1.dtypes == 'O' :
        input.replace({'mag1_1' : {'-' : -0}}, inplace=True)
        input.replace({'mag1_1' : {'A' : -1}}, inplace=True)
        input.replace({'mag1_1' : {'B' : -2}}, inplace=True)
        input.replace({'mag1_1' : {'C' : -3}}, inplace=True)
        input.replace({'mag1_1' : {' ' : nan}}, inplace=True)
        input.replace({'mag1_2' : {' ' : nan}}, inplace=True)
    input.mag1_1 = input.mag1_1.astype("float64")
    input.mag1_2 = input.mag1_2.astype("float64")
    input.mag1_1 = input["mag1_1"].where(input["mag1_1"] >= 0 , input["mag1_1"] - ( input["mag1_2"] / 10.0 ))
    input.mag1_1 = input["mag1_1"].where(input["mag1_1"] < 0 , input["mag1_1"] + ( input["mag1_2"] / 10.0 ))
    return input

def minute(input) :
    # 秒を直す。
    # 震源固定の場合は小数点以下空白
    # 震源固定は震源評価9番。
    input.second.where(input.hypo_judge == 9, input.second * 0.01, inplace=True )
    return input

def depth(input) :
    # 深さを直す
    # 深さフリーならF5.2
    # 深さ固定ならI3
    # 深さフリーは震源評価1番
    input.depth.mask(input.hypo_judge == 1, input.depth * 0.01, inplace=True )
    input.depth.mask(input.hypo_judge == 10, input.depth * 0.01, inplace=True )
    return input

def intensity_obs(input) :
    # 震央地名、観測点数、震源決定フラグを分割
    # 震源決定フラグ：最後の1文字
    # 観測点数：5文字
    # 震央地名は残り
    input.determination_way = input["hypo_locale"].str[-3]
    input.obs_number = input["hypo_locale"].str[-8:-3]
    input.hypo_locale = input["hypo_locale"].str[:-8].replace(" ",'')
    return input

def fmt_id_datetime(input) :
    # レコード部分をフォーマットとして利用
    #input.id = input["recode"].str + input["year"].str + input["month"].str + input["day"].str + input["hour"].str + input["minute"].str + input["second"].str
    input.id = input["recode"] + input["year"] + input["month"] + input["day"] + input["hour"] + input["minute"] + input["second"]
    # 日付時刻を変換
    # YYYY-MM-DDThh:mm:ssZ
    input.datetime = input["year"].astype(object) + input["month"].astype(object) + input["day"].astype(object) + input["hour"].astype(object) + input["minute"].astype(object) + input["second"].astype(object).str[0:2] + "+9:00"
    #input.datetime = datetime.strptime(str(input['datetime'].str), '%Y%m%d%H%M%S').isoformat()
    input.datetime = pd.to_datetime(input["datetime"])
    #input.datetime = input["datetime"].tz_localize('Asia/Tokyo')

    #input['datetime'].str.cat([input["year"].str, input["month"].str, input["day"].str, input["hour"].str, input["minute"].str,input["second"].str])
    #_time = datetime.strptime(input["year"].str+input["month"].str+input["day"].str+input["hour"].str+input["minute"].str+input["second"].str,'%Y%m%d%H%M%S')
    #_time = datetime.strptime(input["year"] + input["month"] + input["day"] + input["hour"] + input["minute"] + input["second"], '%Y%m%d%H%M%S')
    #input.datetime = datetime.strptime(input['datetime'], '%Y%m%d%H%M%S').isoformat()

    return input

def convert_JMA_stationList():
    with open(os.path(base_dir,data_dir,filename), encoding='utf-8', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        # ヘッダ行だけを読み込んで、スペース区切りで表示
        header = next(reader)
        #print(' '.join(header))
        for cols in reader:
            #print(cols)
            print("<https://seismic.balog.jp/resource/" + cols[0] + "> a jpe:observer ;")
            print('    schema:spatial "' + cols[1] + '"@ja ;')
            print('    skos:prefLabel "' + cols[2] + '"@ja ;')
            print('    schema:address "' + cols[3] + '"@ja ;')
            print('    schema:latitude ' + cols[4] + ' ;')
            print('    schema:longitude ' + cols[5] + ' ;')
            if cols[7] :
                print('    schema:availabilityStarts "' + cols[6] + '" ;')
                print('    schema:availabilityEnds "' + cols[7] + '" .')
            else :
                print('    schema:availabilityStarts "' + cols[6] + '" .')
            print()

def convert_JMA_code_p():
    with open(os.path.join(base_dir,data_dir,filename), encoding='sjis', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        # ヘッダ行だけを読み込んで、スペース区切りで表示
        #header = next(reader)
        #print(' '.join(header))
        print(prefix_text)
        for cols in reader:
            #print(cols)
            print("<https://seismic.balog.jp/resource/sta-" + cols[0] + "> a jpe:observer ;")
            print('    jpe:stationIdentifier "' + cols[0] + '" ;')
            print('    rdfs:label "' + cols[1] + '"@ja ;')
            print('    skos:prefLabel "' + cols[1] + '"@ja ;')
            print('    schema:latitude ' + cols[2][0:2] + '.' + cols[2][2:4] + ' ;')
            print('    schema:longitude ' + cols[3][0:3] + '.' + cols[3][3:5] + ' ;')
            if cols[5] :
                print('    schema:availabilityStarts "' + cols[4] + '" ;')
                print('    schema:availabilityEnds "' + cols[5] + '" .')
            else :
                print('    schema:availabilityStarts "' + cols[4] + '" .')
            print()

def convert_JMA_hypo_list(_df):
    hypo_data = os.path.join(base_dir,data_dir,filename)
    # 固定長データに分割
    df = read_fixed_hypo(hypo_data)
    # 型を変更する
    df = convert(df)
    # 度分を直す
    df = degree(df)
    # マグニチュードを直す
    df = magnitude(df)
    # 秒を直す
    df = minute(df)
    # 深さを直す
    df = depth(df)
    # 日付時刻を治す
    df = fmt_id_datetime(df)
    # FAR FIELDは削除する
    df = df[df.hypo_locale != "FAR FIELD"]
    # 出力
    df2 = df.round(4)
    df2 = df2.drop(columns=['latitude_min','longitude_min', 'mag1_2'])
    #
    # df2.to_csv(str(input) + ".csv", index=None, header=None)
    #df2.to_csv("test.csv", index=None)
    #print(df2)
    #df2.applymap(convert_JMA_hypo_list)
    #print(df2.applymap(convert_JMA_hypo_list))
    #print(map(convert_JMA_hypo_list, df2))

###
# 震度データの震源
###
def convert_JMA_i_hypo2ttl(input) :
    #_ttl = "<https://seismic.balog.jp/resource/" + input["id"].str + "> a jpe:hypocenter .\n"
    #_ttl += '    skos:prefLabel "' + input["hypo_locale"].str + '"@ja ;\n'
    #_ttl += '    skos:altLabel "' + input["hypo_locale"].str + '"@ja ;\n'
    #_ttl += '    jpe:originTime "' + input["datetime"].str + '" ;\n'
    #_ttl += input["latitude_deg"].where(input["latitude_deg"].notnull() , '    schema:latitude ' + input["latitude_deg"].str + ' ;\n')
    #_ttl += '    schema:longitude ' + input["longitude_deg"].astype(object) + ' ;\n'
    #_ttl += '    jpe:magnitude ' + input["mag1_1"].astype(object) + ' ;\n'
    #_ttl += '    jpe:depth "' + input["depth"].astype(object) + ' ;\n'
    #_ttl += '    jpe:calcShindo "' + input["max_coefficient"].astype(object) + ' ;\n'

    ttl_list = []
    for i, row in input.iterrows():
        _ttl = "<https://seismic.balog.jp/resource/" + str(row.id) + "> a jpe:hypocenter ;\n"
        _ttl += '    rdfs:label "' + str(row.hypo_locale).replace(" ",'') + '"@ja ;\n'
        _ttl += '    skos:altLabel "' + str(row.hypo_locale).replace(" ",'') + '"@ja ;\n'
        _ttl += '    jpe:hypocenterKinds "' + hypocenter_kinds_text[str(row.recode)] + '" ;\n'
        if row.determination_way != nan and row["determination_way"] != ' ':
            _ttl += '    jpe:determinatedWay "' + determinated_way_text[str(row.determination_way)] + '" ;\n'
        _ttl += '    jpe:originTime "' + str(row.datetime) + '" ;\n'
        if 'latitude_deg' in row :
            if 'latitude_min' in row :
                _ttl += '    schema:latitude ' + str(row.latitude_deg) + '.' + str(row.latitude_min) + ' ;\n'
            else :
                _ttl += '    schema:latitude ' + str(row.latitude_deg) + ' ;\n'
        if 'longitude_deg' in row :
            if 'longitude_min' in row :
                _ttl += '    schema:longitude ' + str(row.longitude_deg) + '.' + str(row.longitude_min) + ' ;\n'
            else :
                _ttl += '    schema:longitude ' + str(row.longitude_deg) + ' ;\n'
        if 'mag1_1' in row :
            if 'mag1_2' in row :
                _ttl += '    jpe:magnitude ' + str(row.mag1_1) + '.' + str(row.mag1_2) + ' ;\n'
            else :
                _ttl += '    jpe:magnitude ' + str(row.mag1_1) + ' ;\n'
        if 'mag2_1' in row :
            if 'mag2_2' in row :
                _ttl += '    jpe:magnitude ' + str(row.mag2_1) + '.' + str(row.mag2_2) + ' ;\n'
            else :
                _ttl += '    jpe:magnitude ' + str(row.mag2_1) + ' ;\n'
        # 震度が数値じゃない場合あり
        if row.max_coefficient != nan and row["max_coefficient"] != ' ':
            _ttl += '    jpe:shindo "' + max_coefficient_text[str(row.max_coefficient)] + '" ;\n'
        if row.travel_time != nan and str(row['travel_time']) != ' ' and int(row['travel_time']) > 0:
            _ttl += '    jpe:withTravelTimeTable "' + travel_time_table[int(row.travel_time)] + '" ;\n'
        else :
            _ttl += '    jpe:withTravelTimeTable "' + travel_time_table[0] + '" ;\n'
        if row.obs_number != nan and row['obs_number'] != ' ':
            _ttl += '    jpe:observedStationNum ' + str(row.obs_number).replace(" ",'') + ' ;\n'
        _ttl += '    jpe:depth ' + str(row.depth) + ' .\n'
        #print(_ttl)
        ttl_list.append(_ttl)

    return ttl_list

###
# 震度データの観測波形
###
def convert_JMA_i_obs2ttl(input) :
    ttl_list = []
    for i, row in input.iterrows():
        _ttl = "<https://seismic.balog.jp/resource/" + str(row.obs_id) + "-" + str(row.hypo_id) + "> a jpe:observedWave ;\n"
        _ttl += '    schema:startTime "' + str(row.startTime) + '" ;\n' # 日付時刻の型を決める
        if row.max_coefficient != nan :
            _ttl += '    jpe:Shindo ' + str(row.max_coefficient) + ' ;\n'
        if row.calcShindo != nan :
            _ttl += '    jpe:calcShindo ' + str(row.calcShindo)[0] + "." + str(row.calcShindo)[1] + ' ;\n'
        _ttl += '    jpe:hasHypocenter <https://seismic.balog.jp/resource/' + str(row.hypo_id) + '> ;\n'
        _ttl += '    jpe:observedBy <https://seismic.balog.jp/resource/sta-' + str(row.obs_id) + '> .\n'
        #print(_ttl)
        ttl_list.append(_ttl)

    return ttl_list

def convert_JMA_i_obs(_filename) :
    df = pd.DataFrame(columns=fixed_i_hypo_names)
    df_obs = pd.DataFrame(columns=fixed_i_obs_names)
    record = ['' for k in range(len(fixed_i_hypo_width))]
    record_obs = ['' for k in range(len(fixed_i_obs_width))]

    with open(os.path.join(base_dir,data_dir,shindo_dir,_filename), encoding='sjis', newline='') as f:
        reader = f.readlines()
        _hypo_id = ''
        obs_num = 1
        for line in reader :
            if re.match("[ABD]",str(line[0:1])) :
                if obs_num == 0 :
                    continue
                #print(line)
                # 地震のIDとして最初のレコードをセット
                _hypo_id = line[0:17]
                obs_num = 0
                pos = 0 # 各行の実質データはPython でいう0、ふつうにいえば1文字めからはじまる
                # 要素ごとに record に入れる
                for k in range(len(fixed_i_hypo_width)):
                    record[k] = line[pos:pos+fixed_i_hypo_width[k]]
                    pos = pos + fixed_i_hypo_width[k]
                    #print(record[k])
                # 1行ずつ df に追加する
                df = df.append(pd.Series(record, index=df.columns), ignore_index=True)
                last_obs_num = int(line[-7:-3])
            else :
                obs_num += 1
                #print(_hypo_id)
                #print(line)
                pos = 0 # 各行の実質データはPython でいう0、ふつうにいえば1文字めからはじまる
                # 要素ごとに record に入れる
                for k in range(len(fixed_i_obs_width)):
                    record_obs[k] = line[pos:pos+fixed_i_obs_width[k]]
                    pos = pos + fixed_i_obs_width[k]
                    #print(record_obs[k])
                    if pos > len(line) :
                        break
                # 最後のカラムに震源を追加
                record_obs[-2] = _hypo_id
                # 最後のカラムに日付時刻
                record_obs[-1] = pd.to_datetime(_hypo_id[1:7] + record_obs[2] + record_obs[3] + record_obs[4] + record_obs[5][0:2] + "+9:00")
                # 1行ずつ df に追加する
                df_obs = df_obs.append(pd.Series(record_obs, index=df_obs.columns), ignore_index=True)

    print(df)
    print(df_obs)
    # 型を変更する
    df = convert(df)
    # 度分を直す
    df = degree(df)
    # マグニチュードを直す
    df = magnitude(df)
    # 秒を直す
    #df = minute(df)
    # 深さを直す
    df = depth(df)
    # 震央地名、観測点数、震源決定フラグを修正
    df = intensity_obs(df)
    # 日付時刻を治す
    df = fmt_id_datetime(df)
    # FAR FIELDは削除する
    df = df[df.hypo_locale != "FAR FIELD"]
    # 出力
    df2 = df.round(4)
    df2 = df2.drop(columns=['latitude_min','longitude_min', 'mag1_2'])
    #print(df2)

    i_hypo_ttl = convert_JMA_i_hypo2ttl(df2)
    i_obs_ttl = convert_JMA_i_obs2ttl(df_obs)

    with open(os.path.join(base_dir,data_dir,shindo_dir,_filename+'_i.ttl'), 'w') as f:
        f.writelines(prefix_text)
        f.writelines(i_hypo_ttl)

    with open(os.path.join(base_dir,data_dir,shindo_dir,_filename+'_i_obs.ttl'), 'w') as f:
        f.writelines(prefix_text)
        f.writelines(i_obs_ttl)

if __name__ == "__main__":

    #convert_JMA_code_p()

    filename = 'i2019.dat'
    #for i in [9,8,7] :
    for i in [6,5,4,3,2] :
    #for i in [6,5,4,3,2,1,0] :
        filename = 'i201' + str(i) + '.dat'
        print(filename)
        convert_JMA_i_obs(filename)
