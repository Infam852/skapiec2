# Optymalizator zakupów Skąpiec.pl    

Projekt ma na celu zooptymalizowanie zakupów na portalu Skąpiec.pl poprzez dodanie 
możliwości wyszukiwania ofert z uwzględnieniem kryteriów takich jak: 
* zakres cen
* reputacja sklepu
* ilość ocen sklepu

Działanie systemu:  
System dostaje od użytkownika listę produktów, które go interesują (maksymalnie 5). 
Następnym krokiem jest zebranie ze strony Skąpiec.pl potrzebnych informacji na temat wyszukanych produktów lub ich braku. 
Wyszukane informację przekazywane są do algorytmu, który zwraca 3 najlepsze zestawy produktów.

### Instalacja
W celu uruchomienia programu należy:
* zainstalować potrzebne moduły (plik requirements.txt)
* python main.py - powoduje uruchomienie lokalnego serwera na porcie 5000 
* w przeglądarce "localhost:5000"

### Zasada działania
Użytkownik wprowadza produkty do koszyka podając ich nazwę, zakres cen, ilość, minimalną reputację i minimalną ilość ocen sprzedawcy. Po wprowadzeniu produktów system rozpoczyna wyszukiwanie żądanych produktów. Następnie klient otrzymuje 3 zestawy produktów, które są uznane za "najlepsze" przez system.

### Ograniczenia
* struktura strony Skąpiec.pl wymaga wielu zapytań HTTP w celu pobrania niezbędnych infomracji, co mocno wpływa na wydajnośc systemu
* strona Skąpiec.pl nie umożliwia filtrowania produktów w podanym zakresie cen 
* nieudana próba otrzymania dostępu do API 
