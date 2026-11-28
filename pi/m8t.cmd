# u-blox NEO-M8T commands, sent by rtkrcv when the rover starts.
# They set up everything rtkrcv needs, so the rover still works after the
# receiver loses its saved settings. Changes last until the next power cycle.
# CFG-MSG fields: class id I2C UART1 UART2 USB SPI reserved (rate per port)

# 1 Hz measurement rate
!UBX CFG-RATE 1000 1 1

# raw measurements (RXM-RAWX) and navigation subframes (RXM-SFRBX) on UART1
!UBX CFG-MSG 2 21 0 1 0 0 0 0
!UBX CFG-MSG 2 19 0 1 0 0 0 0

# time marks (TIM-TM2) on UART1
!UBX CFG-MSG 13 3 0 1 0 0 0 0

# NMEA GGA, GLL, GSA, GSV, RMC, VTG off on UART1 only, to keep the 115200 baud
# link for UBX; I2C, USB and SPI keep their default rate of 1
!UBX CFG-MSG 240 0 1 0 0 1 1 0
!UBX CFG-MSG 240 1 1 0 0 1 1 0
!UBX CFG-MSG 240 2 1 0 0 1 1 0
!UBX CFG-MSG 240 3 1 0 0 1 1 0
!UBX CFG-MSG 240 4 1 0 0 1 1 0
!UBX CFG-MSG 240 5 1 0 0 1 1 0
