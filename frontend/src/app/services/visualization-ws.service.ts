import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';
import {Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class VisualizationWsService {
  baseUrl = environment.baseUrl;

  constructor() { }

  url = 'ws'+this.baseUrl.replace('http','').replace('https','') + '/ws/';

  ws: WebSocket;
  socketIsOpen = 1;
  connected= true; 

  createObservableSocket(): Observable<any> {
     this.ws = new WebSocket(this.url);
    return new Observable(
       observer => {

        this.ws.onmessage = (event) =>
          observer.next(event.data);

        this.ws.onerror = (event) => observer.error(event);

        this.ws.onclose = (event) => observer.complete();
        
        return () =>
            this.ws.close(1000, "The user disconnected");
       }
    );
  }

  sendMessage(topic: string, isClassification: boolean): boolean {
    if (this.ws.readyState === this.socketIsOpen) {
       var jsonData = {"topic": topic, "classification": isClassification};
       this.ws.send(JSON.stringify(jsonData));
       return true;
    } else {
      return false;
     }
  }
}
