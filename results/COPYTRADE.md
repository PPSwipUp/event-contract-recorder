# Copy-trading Polymarket's top wallets: out-of-sample test

Universe 616 wallets (top 500 by volume + top 200 by profit); resolved buys: 2,180,032

Eligible on A (>= 50 resolved buys, >= 10 markets): 398; with >= 50 buys in B too: 314

Persistence: rank correlation of copy return A vs B = 0.168

## Top 20 picked on A (Jan-Apr 2026), copied on B (May-Sep 2026) at THEIR price (zero delay)

- On A (in-sample): mean return per copied trade 260.2% (median wallet 119.8%)
- On B (out-of-sample): 33,259 trades, mean return per copied trade -22.06%, $100/trade -> total $-733,776, weekly t -2.24, positive weeks 26%
- Benchmark: copying ALL eligible wallets on B: mean -8.49% per trade over 794,774 trades

Per picked wallet:

| wallet                                     |    n |   markets |   roi_c |   n_B |   markets_B |   roi_c_B |
|:-------------------------------------------|-----:|----------:|--------:|------:|------------:|----------:|
| 0x7b02b2bac2a30ed5e40b7094e734f4c3dc2a4991 | 3237 |        53 | 1462.63 |  2376 |          13 |    -18.51 |
| 0xf49ce459b52f60b70ce0fe9aa6203e6bf90f9786 | 3160 |        29 |  829.31 |  2855 |          32 |   -103.02 |
| 0xb886580698ede4b18de3e446b2d8da8bcedd81b3 | 2930 |        80 |  511.03 |   299 |          12 |    -36.45 |
| 0x8f41129e43ebfbfe6075d0804f3b2bb763b3260e | 2779 |        40 |  413.31 |  2513 |         784 |    -13.01 |
| 0x8a4c788f043023b8b28a762216d037e9f148532b | 1299 |        56 |  378.66 |   945 |          64 |      4.58 |
| 0x5188fa0e8a77e87bc6a58e6781fdfc4e165cc804 | 3270 |        92 |  252.39 |  2273 |         250 |    -13.29 |
| 0x51fd8f0358cc9e8a1ee5f87a0c7e3b07ed634272 | 2835 |       113 |  140.18 |  1019 |         194 |    -67.62 |
| 0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5 | 3041 |       131 |  137.12 |  3112 |         210 |     27.41 |
| 0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292 | 2400 |        51 |  123.28 |  2561 |         108 |     44.7  |
| 0x1cc16713196d456f86fa9c7387dd326a7f73b8df | 3253 |        33 |  122.83 |  1465 |          62 |     12.54 |
| 0x997cda7b31612e3c394bfb55440619f3f689251e | 3207 |        50 |  116.74 |  2802 |         120 |    -49.98 |
| 0x93c22116e4402c9332ee6db578050e688934c072 | 3469 |        67 |   99.17 |   nan |         nan |    nan    |
| 0x876426b52898c295848f56760dd24b55eda2604a | 3490 |        38 |   91.81 |   nan |         nan |    nan    |
| 0xea8ee311382139d952087a669252252625663de0 |  542 |       200 |   89.76 |  3419 |        2999 |    -45.57 |
| 0xa9b44dca52ed35e59ac2a6f49d1203b8155464ed | 2813 |       132 |   86.88 |   nan |         nan |    nan    |
| 0xf68a281980f8c13828e84e147e3822381d6e5b1b | 3035 |       318 |   81.85 |  1314 |         297 |     -0.26 |
| 0x6b7c75862e64d6e976d2c08ad9f9b54add6c5f83 | 3250 |       337 |   75.14 |   nan |         nan |    nan    |
| 0x849ccb5907938ce8be18ed5dbf583288e2da4009 | 3104 |        86 |   70.41 |  2812 |         128 |    -49.06 |
| 0x0fe40e887acbd0022f89d996acce26ab428501b7 | 3493 |        97 |   60.75 |  3494 |          80 |    -11.82 |
| 0x916f7165c2c836aba22edb6453cdbb5f3ea253ba | 3480 |        28 |   59.76 |   nan |         nan |    nan    |

B returns of the picked wallets by category:

| category   | size   | mean   |
|------------|--------|--------|

B returns by entry price:

| price       |   size |   mean |
|:------------|-------:|-------:|
| (0.0, 0.1]  |  11638 | -60.64 |
| (0.1, 0.3]  |   6073 | -18.44 |
| (0.3, 0.5]  |   4838 |   7.13 |
| (0.5, 0.7]  |   3337 |   4.07 |
| (0.7, 0.9]  |   3497 |   6.91 |
| (0.9, 0.97] |   1975 |   5.02 |
| (0.97, 1.0] |   1901 |   0.92 |
