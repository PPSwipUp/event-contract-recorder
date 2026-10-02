| fill rule                                        | minutes   |   fills |   contracts |   c_per_contract |   pred_edge_c |   $_per_month_if_every_hour |   day_t |
|:-------------------------------------------------|:----------|--------:|------------:|-----------------:|--------------:|----------------------------:|--------:|
| naive: only takers on our side, print-sized      | all       |   32210 |      325533 |            -4.91 |          9.79 |                      -14610 |  -12.74 |
| naive: only takers on our side, print-sized      | 10-20     |    1488 |       16664 |            -4.11 |          9.86 |                        -627 |   -1.63 |
| + pick-off of whole order on prints >=3c through | all       |   22711 |      390670 |            -4.67 |          9.69 |                      -16686 |  -14.12 |
| + pick-off of whole order on prints >=3c through | 10-20     |    1244 |       20988 |            -3.15 |          9.86 |                        -606 |   -1.41 |
| + other traders' orders crossing us (50%)        | all       |   44245 |      452872 |            -4.4  |          9.49 |                      -18240 |  -16.11 |
| + other traders' orders crossing us (50%)        | 10-20     |    2941 |       32567 |            -3.34 |          9.7  |                        -994 |   -1.99 |
| all (base case)                                  | all       |   24847 |      496008 |            -3.92 |          9.32 |                      -17765 |  -13.63 |
| all (base case)                                  | 10-20     |    2037 |       42520 |            -2.94 |          9.51 |                       -1145 |   -2.05 |
