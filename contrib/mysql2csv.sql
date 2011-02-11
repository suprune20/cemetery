select counter, case when N_v_z then convert(N_v_z using utf8) else N end as n, convert(Family using utf8) as ln, convert(name using utf8) as fn, convert(patronymic using utf8) as ptrc, convert(Initial using utf8) as initials, Date_z as bur_date, convert(N_u4astka using utf8) as area, convert(Rjad using utf8) as row, convert(N_mogily using utf8) as seat, convert(Family_z using utf8) as cust_ln, '' as cust_fn, '' as cust_ptrc, convert(Initials_z using utf8) as cust_initials, convert(Gorod using utf8) as city, convert(Strit using utf8) as street, convert(Dom using utf8) as house, Korpus as block, Kvartira as flat, case when N_v_z then convert(concat("kombinat:", N_v_z, ". ", Zametki) using utf8) else convert(Zametki using utf8) end as comment INTO OUTFILE 'D:\uruchye.csv' FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\' LINES TERMINATED BY '\r\n' from kladbische.burial WHERE burial_jurnal_id = 18;
