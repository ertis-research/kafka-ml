import { Component, OnInit } from '@angular/core';
import { state, trigger, style } from '@angular/animations';
import {MatSnackBar} from '@angular/material/snack-bar';
import {VisualizationWsService}  from '../services/visualization-ws.service';
import {Subscription} from "rxjs";
import { MatTableDataSource } from '@angular/material/table';


@Component({
  animations: [
    trigger('openClose', [
      state('init', style({
        height: '200px',
        backgroundColor: '#D3D3D3'
      }))
    ]),
  ],
  selector: 'app-visualization',
  templateUrl: './visualization.component.html',
  styleUrls: ['./visualization.component.css']
})
export class VisualizationComponent implements OnInit {
  INIT_COLOR: string = '#D3D3D3';
  displayedColumns = ['one','two','three','four'];
  dataSource = new MatTableDataSource();
  wsSubscription: Subscription;
  isOpen = true;
  config: string;
  color: string = this.INIT_COLOR;
  validConfig: JSON;
  state: string = 'init';
  topic: string = '';
  connected: boolean = false;
  topicConfigured: boolean = false;
  workingCondition: string = '';
  dic = {}
  total = 0.0;
  average_updated: boolean = false;
  average_window: number;

  // chart options 
  legend: boolean = true;
  showLabels: boolean = true;
  animations: boolean = false;
  xAxis: boolean = true;
  yAxis: boolean = true;
  showYAxisLabel: boolean = true;
  showXAxisLabel: boolean = true;
  timeline: boolean = true;
  view: any[] = [700, 300];
  showXAxis = true;
  showYAxis = true;
  gradient = false;
  showLegend = true;
  analysisData: any [];
  isClassification: boolean = false;
  isRegression: boolean = false;

  colorScheme = {
    domain: []
  };
  
  constructor(private wsService: VisualizationWsService, private snackbar: MatSnackBar) { }
  
  
  ngOnInit(): void {
    this.dic={};
    this.analysisData = []; 
    this.dataSource.data=[{'c1': '', 'c2': '', 'c3': '', 'c4': '', 
    "color_1": this.INIT_COLOR, "color_2": this.INIT_COLOR, "color_3": this.INIT_COLOR, 
    "color_4": this.INIT_COLOR, }];
  }

  ngOnDestroy(): void{
    this.closeWS();
  }

  onResize(event) {
    this.view = [event.target.innerWidth * 0.50, 400];
  }

  setConfig(): void{
    try {
      this.validConfig= JSON.parse(this.config);
      this.closeWS();
      this.isClassification=false;
      this.isRegression=false;
      if (this.validConfig['type']=='classification'){
        this.setClassificationConfig();
        this.isClassification=true;
      
      }else if (this.validConfig['type']=='regression'){
        this.setRegressionConfig();
        this.isRegression=true;
      }else
        throw "Type not recognized, available types: classification and regressions"; 
      
        this.snackbar.open('Configuration set correctly', '', {
          duration: 2000
        });
    } catch (e) {
      this.snackbar.open('Configuration not valid: ['+e+']', '', {
        duration: 2000
      });
    }
  }

  /*
  * Regressions functions
  */ 
  setRegressionConfig(): void{
    var labels= this.validConfig['labels'];
    this.average_updated = this.validConfig['average_updated'];
    this.total=0.0;
    this.dic={};
    this.analysisData = []; 
    for (let x in labels){
        this.analysisData.push(
          {
            "name": labels[x]["label"],
            "series": []
          });
          this.colorScheme.domain.push(labels[x]["color"]);
    }
  }
  regressionData(data){
    var jdata= JSON.parse(data);
    for (var i = 0; i < jdata['values'].length; i++) { 
      this.analysisData[i]['series'].push(
        {
          "value": jdata['values'][i],
          "name": this.analysisData[i]['series'].length
      })
    }
    this.analysisData = [...this.analysisData];
  }

  /*
  * Classification functions
  */

  updateClassificationLast(workingCondition, color){
    for (var i=3; i>=1; i--){
      this.dataSource.data[0]["c"+(i+1)]= this.dataSource.data[0]["c"+(i)]
      this.dataSource.data[0]["color_"+(i+1)]= this.dataSource.data[0]["color_"+(i)]
    }
    this.dataSource.data[0]["c1"]= workingCondition;
    this.dataSource.data[0]["color_1"]= color;
  }

  findValue(id){
    for (var i in this.dic){
      if (this.dic[i]['label']==id)
        return this.dic[i]['value'];
    }
  }

  updateClassificationData(id){
    let i=0;
    let max=0.0;
    let i_max=0;
    let color;
    while (i<this.analysisData.length){
        if (i in this.dic)
          this.analysisData[i]['value']=(this.dic[i]['value']/this.total).toFixed(4);
        else
          this.analysisData[i]['value']=(this.findValue(this.analysisData[i]['name'])/this.total).toFixed(4);
        if(this.analysisData[i]['value']>max){
          max=this.analysisData[i]['value'];
          i_max=i;
          if (i in this.dic)
            color=this.dic[i]['color']
          else
            color=this.findValue(this.analysisData[i]['name']);
        }
        i++;
    }
    if(!this.average_updated){
      this.updateClassificationLast(this.workingCondition, this.color);
      this.workingCondition=this.dic[id]['label'];
      this.color=this.dic[id]['color'];
    }
    else if(this.analysisData[i_max]['name'] != this.workingCondition || this.total%this.average_window==0){
      this.updateClassificationLast(this.workingCondition, this.color);
      this.workingCondition=this.analysisData[i_max]['name'] ;
      this.color=color;
    }
    this.analysisData = [...this.analysisData];
      
  }

  setClassificationConfig(): void{
    var labels= this.validConfig['labels'];
    this.average_updated = this.validConfig['average_updated'];
    this.total=0.0;
    this.dic={};
    this.analysisData = []; 
    if( this.average_updated){
      this.average_window = this.validConfig['average_window'];
    }
    for (let x in labels){
      this.dic[labels[x]["id"]]=
      {
        "color": labels[x]["color"],
        "label": labels[x]["label"],
        "value": 0.0
      }
    }
    for (let x in this.dic){
      this.analysisData.push({
        "name": this.dic[x]['label'],
        "value": this.dic[x]['value']
      })
      this.colorScheme.domain.push(this.dic[x]['color']);
    }
    this.analysisData = [...this.analysisData];
  }

  classificationData(data){
    var id=parseInt(data);
    var value=0;
    if (id in this.dic){
      this.dic[id]['value']=this.dic[id]['value']+1;
    }else{
      this.dic[id]={
        "color": this.INIT_COLOR,
        "label": id,
        "value": 1.0
      }
      this.analysisData.push({
        "name": id,
        "value": this.dic[id]['value']
      })
      this.color=this.INIT_COLOR;
      this.workingCondition=data;
    }
    this.total=this.total+1;
    this.updateClassificationData(id);
  }

  /*
  * Websockets functions
  */
  sendTopic(){
    this.connectWS();
    setTimeout(() => {  this.sendMessageToServer(this.topic); }, 1000);
    
   }

  connect(){
    this.wsSubscription =
      this.wsService.createObservableSocket()
       .subscribe(
        data => {
          if (this.isClassification){
            this.classificationData(data);
          }
          else if (this.isRegression){
            this.regressionData(data);
          }
        },
        err => {this.snackbar.open('Error connecting with the server', '', {
              duration: 3000
            }); this.connected= false;
        },
        () =>  {
          this.snackbar.open('Disconnected from the server', '', {
            duration: 3000
          });
          this.connected= false;
        }
      );
  }
  
  sendMessageToServer(topic){
    if(this.wsService.sendMessage(topic, this.isClassification)){
      this.snackbar.open('Connected to topic: '+this.topic, '', {
        duration: 2000
      });
      this.topicConfigured=true;
    }else{
      this.snackbar.open('Error sending the message', '', {
        duration: 2000
      });
    }
  }

  closeWS(){
    if (this.connected){
      this.wsSubscription.unsubscribe();
      this.connected=false;
      this.topicConfigured=false;
    }
  }
  connectWS(){
    if (!this.connected){
      this.connect();
      this.connected=true;
    }
  }

}
