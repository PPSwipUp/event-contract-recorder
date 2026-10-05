| fill rule                                        | minutes   |   fills |   contracts |   c_per_contract |   pred_edge_c |   $_per_month_if_every_hour |   day_t |
|:-------------------------------------------------|:----------|--------:|------------:|-----------------:|--------------:|----------------------------:|--------:|
| naive: only takers on our side, print-sized      | all       |   48196 |      479624 |            -4.61 |          9.76 |                      -14944 |  -12.27 |
| naive: only takers on our side, print-sized      | 10-20     |    2055 |       22579 |            -2.75 |          9.72 |                        -419 |   -1.29 |
| + pick-off of whole order on prints >=3c through | all       |   33345 |      570583 |            -4.3  |          9.67 |                      -16552 |  -13.53 |
| + pick-off of whole order on prints >=3c through | 10-20     |    1687 |       27953 |            -2.07 |          9.71 |                        -391 |   -1.11 |
| + other traders' orders crossing us (50%)        | all       |   64763 |      657120 |            -3.98 |          9.46 |                      -17662 |  -14.51 |
| + other traders' orders crossing us (50%)        | 10-20     |    3973 |       43393 |            -2.16 |          9.59 |                        -634 |   -1.52 |
| all (base case)                                  | all       |   36144 |      717401 |            -3.48 |          9.3  |                      -16858 |  -13.58 |
| all (base case)                                  | 10-20     |    2769 |       56707 |            -1.73 |          9.44 |                        -661 |   -1.39 |
