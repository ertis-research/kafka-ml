import { Injectable } from '@angular/core';
import { HttpClient } from  '@angular/common/http';

import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})

export class IoTDeviceService {

  baseUrl = environment.baseUrl;

  constructor(private httpClient: HttpClient) { }

    url = this.baseUrl + '/iot-devices/';
    
    getIoTDevices(){
      return this.httpClient.get<JSON[]>(this.url);
    }
    

    createIoTDevice(data: JSON){
      return this.httpClient.post<JSON>(this.url, data)
    }

    getIoTDevice(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.get(url);
    }

    deleteIoTDevice(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.delete<JSON>(url);
    }

    editIoTDevice(id: number, data: JSON){
      const url = `${this.url}${id}`
      return this.httpClient.put<JSON>(url, data);
    }

}
