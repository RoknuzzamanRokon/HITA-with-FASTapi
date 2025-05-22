content/get_all_hotel_only_supplier/

{
  "provider_property": [
    {
      "provider_name": "tbohotel"
    }
  ]
}

then need get result like this 
{
  "hotel": [
    {
      "ittid": 1,
      "name": "Hotel A",
      "country_name": "Country A",
      "country_code": "CA",
      "type": "hotel",
      "provider": [{"name": "tbohotel",
                    "provider_id": 1,
                    "status": "update",}],
      "location": [{"id": 1,
                    "name": "City A",
                    "location_id": 1,
                    "status": "update",
                    "latitude": 12.34,
                    "longitude": 56.78,
                    "address": "123 Street, City A",
                    "postal_code": "12345",
                    "city_id": 1,
                    "city_name": "City A",
                    "city_code": "CA",
                    "state": "State A",
                    "country_name": "Country A",
                    "country_code": "CA"
                    }],
        "contract": [{"id": 1,
                      "phone" : ["1234567890"],
                      "email" : ["contact@hotela.com"],
                      "website" : ["www.hotela.com"],
                      "fax" : ["0987654321"],
                    }],
    },
    {
      "ittid": 2,
      "name": "Hotel B",
        "country_name": "Country B",
        "country_code": "CB",
        "type": "hotel",
      "provider": [{"name": "tbohotel",
                    "provider_id": 1,
                    "status": "update",}],
      "location": [{"id": 2,
                    "name": "City B",
                    "location_id": 2,
                    "status": "update",
                    "latitude": 23.45,
                    "longitude": 67.89,
                    "address": "456 Avenue, City B",
                    "postal_code": "67890",
                    "city_id": 2,
                    "city_name": "City B",
                    "city_code": "CB",
                    "state": "State B",
                    "country_name": "Country B",
                    "country_code": "CB"
                    }],
        "contract": [{"id": 2,
                      "phone" : ["0987654321"],
                      "email" : ["contact@hotelb.com"],
                      "website" : ["www.hotelb.com"],
                      "fax" : ["1234567890"],
                    }],
    }