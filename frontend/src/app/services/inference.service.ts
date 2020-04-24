import { Injectable } from '@angular/core';
import { HttpClient } from  '@angular/common/http';
import { environment } from '../environment';

@Injectable({
  providedIn: 'root'
})

export class InferenceService {

  baseUrl = environment.baseUrl;

  constructor(private httpClient: HttpClient) { }

    url = this.baseUrl + '/inferences/';
    
    getInferences(){
      return this.httpClient.get<JSON[]>(this.url);
    }

    stopInference(data){
      return this.httpClient.post<JSON[]>(this.url, data);
    }

}
