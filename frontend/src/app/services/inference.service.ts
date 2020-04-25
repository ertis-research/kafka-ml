import { Injectable } from '@angular/core';
import { HttpClient } from  '@angular/common/http';
import { environment } from '../../environments/environment';

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

    deleteInference(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.delete(url);
    }

    stopInference(id: number){
      const url = `${this.url}${id}`
      return this.httpClient.post(url, null);
    }

}
