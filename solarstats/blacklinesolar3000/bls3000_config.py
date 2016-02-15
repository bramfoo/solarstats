# BlackLine Solar 3000 port and value maps
portContents = {0x0A : 'VoltsPV1',
                0x0B : 'VoltsPV2',
                0x0C : 'CurrentPV1',
                0x0D : 'CurrentPV2',
                0x0E : 'VoltsAC1',
                0x0F : 'VoltsAC2',
                0x10 : 'VoltsAC3',
                0x11 : 'CurrentAC1',
                0x12 : 'CurrentAC2',
                0x13 : 'CurrentAC3',
                0x14 : 'FrequencyAC',
                0x15 : 'PowerAC',
                0x16 : 'PowerAC',
                0x17 : 'EnergyToday',
                0x18 : 'EnergyTotal',
                0x19 : 'EnergyTotal',
                0x1A : 'MinToday',
                0x1B : 'MinToday',
                0x1C : 'HrsTotal',
                0x1D : 'HrsTotal',
                0x1E : 'Temperature',
                0x1F : 'Iac-Shift',
                0x20 : 'blank',
                0x21 : 'blank',
                0x22 : 'DCI',
                0x23 : 'blank',
                0x24 : 'blank',
                0x25 : 'blank',
                0x26 : 'blank',
                0x27 : 'Status1',
                0x28 : 'Status2',
                }

scaleFactors = {'VoltsPV1'      : 10.0,
                'VoltsPV2'      : 10.0,
                'CurrentPV1'    : 10.0,
                'CurrentPV2'    : 10.0,
                'VoltsAC1'      : 10.0,
                'VoltsAC2'      : 10.0,
                'VoltsAC3'      : 10.0,
                'CurrentAC1'    : 10.0,
                'CurrentAC2'    : 10.0,
                'CurrentAC3'    : 10.0,
                'FrequencyAC'   : 100.0,
                'PowerAC'       : 10.0,
                'EnergyToday'   : 10.0,
                'EnergyTotal'   : 10.0,
                'MinToday'      : 1.0,
                'HrsTotal'      : 1.0,
                'Temperature'   : 10.0,
                'Iac-Shift'     : 1.0,
                'blank'         : 1.0,
                'blank'         : 1.0,
                'DCI'           : 1.0,
                'Status1'       : 1,
                'Status2'       : 1,
                }


"""
===
BLS decoding
===
Commands
  SA =slaveAddress; FC=functionCode SR=startRegister, NR=numRegisters CR=crc
  SA FC SR SR NR NR CR CR
  02 03 00 26 00 17 E4 3C
  FF 03 00 3C 00 01 51 D8 - busQuery
  02 04 00 00 00 03 B0 38 - serial number
  02 04 00 0A 00 1F 91 F3 - inverter data
  02 04 00 29 00 1F 60 39
  02 04 00 2B 00 02 01 F0 - model / SW version
  02 04 00 3A 00 17 90 3A

Holding registers (0x03)
26
27
28
29
2A
2B
2C
2D
2E
2F
30
31
32
33
34
35
36
37
38
39
3A
3B
3C  ? Bus address   00 02

Input registers (0x04)
Reg Description Value
00  Serial No   42 06
01  Serial No   12 43
02  Serial No   50 30
03  ?       FF FF
04  ?       FF FF
05  ?       FF FF
06  ?       FF FF
07  ?       FF FF
08  ?       FF FF
09  ?       FF FF
0A  VoltsPV1, 10
0B  VoltsPV2, 10
0C  CurrentPV1, 10
0D  CurrentPV2, 10
0E  VoltsAC1, 10
0F  VoltsAC2, 10
10  VoltsAC3, 10
11  CurrentAC1, 10
12  CurrentAC2, 10
13  CurrentAC3, 10
14  Frequency, 100
15  PowerAC, 10
16  PowerAC, 10
17  EnergyTodayAC, 10
18  EnergyTotalAC, 10
19  EnergyTotalAC, 10
1A  TimeToday
1B  TimeToday, 1 (min)
1C  TimeTotal, 1
1D  TimeTotal, 1 (hr)
1E  Temperature, 10
1F  Iac-Shift, 1    01 FE
20  blank?          00 00
21  blank?          00 00
22  DCI (ma) ??
23      blank?          00 00
24      blank?          00 00
25      blank?          00 00
26      blank?          00 00
27      Status1 (0)     00 00
28  Status2, 1
29  ?Pac?, 10       09 38?
2A  ?BUS?, 10       0E D8?
2B  ModelNo (10)    00 1E
2C  SWversion (100) 01 F7
2D          05 DC
2E          00 3C
2F          07 30
30          06 A4
31          00 10
32          00 0A
33          0A 50
34          0A F0
35          00 10
36          00 0A
37          12 8E
38          11 94
39          00 10
3A          00 0A
3B          13 9C
3C          14 1E
3D          00 10
3E
3F
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
"""
