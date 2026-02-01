#!/bin/bash

#for year in {2000..2023}
#for year in {2015..2023}
for year in {1970..2023}
do
    TTL_FILE="event_${year}_all.ttl"
    if [ ! -f "${TTL_FILE}" ]; then
        echo "${year}年のデータを取得中..."
        echo "time python obspy-clients-fdsn-2.py ${year} > event_${year}_all.ttl"
        python obspy-clients-fdsn-2.py ${year} > ${TTL_FILE}
        if [ $? -eq 0 ]; then
            echo "${TTL_FILE} done!"
        else
            echo "${TTL_FILE} is error, delete tmp ttl file"
            rm ${TTL_FILE}
        fi
    else
        echo "${TTL_FILE}は作成済みです。"
    fi
    sleep 1
done

