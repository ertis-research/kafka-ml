import { Component, OnInit } from '@angular/core';
import { ResultService } from '../services/result.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ActivatedRoute } from '@angular/router';
import { FormGroup, FormControl } from '@angular/forms';
import { NgxChartsModule } from '@swimlane/ngx-charts';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-plot-view',
  templateUrl: './plot-view.component.html',
  styleUrls: ['./plot-view.component.css']
})
export class PlotViewComponent implements OnInit {
  view: any[]; // Preguntar Cristian si fixed o que tome un div-container entero
  colorScheme = {
    domain: ['#FF3333', '#FF33FF', '#CC33FF', '#0000FF', '#33CCFF', '#33FFFF', '#33FF66', '#CCFF33', '#FFCC00', '#FF6600']
  };

  resultID: number;

  available_metrics: string[] = [];

  metrics_retrieved: JSON[];
  conf_matrix_retrieved: JSON[];

  metricListControl = new FormControl([]);
  data_shown: JSON[] = [];

  image:SafeUrl; 

  constructor(private resultService: ResultService,
    private snackbar: MatSnackBar,
    private route: ActivatedRoute, 
    private sanitizer: DomSanitizer) { 
      this.view = [innerWidth * 0.50, 400];
    }

  onResize(event) {
      this.view = [event.target.innerWidth * 0.50, 400];
  }

  refreshData() {
    if (this.route.snapshot.paramMap.has('id')) {
      this.resultID = Number(this.route.snapshot.paramMap.get('id'));
          
      this.resultService.getChartInfo(this.resultID).subscribe((data: JSON[]) => {
        this.metrics_retrieved = data['metrics'];
        let av_mtr = []
        this.metrics_retrieved.forEach(function (value) {
          if (!value["name"].endsWith("_val")) {
            av_mtr.push(value["name"]);
          }
        });
        this.available_metrics = av_mtr;
        
        this.conf_matrix_retrieved = data['conf_mat'];

        this.onFormChange();

        if (this.conf_matrix_retrieved != null) {
          this.resultService.getConfusionMatrix(this.resultID).subscribe(blob => {
            let objectURL = URL.createObjectURL(blob);       
            this.image = this.sanitizer.bypassSecurityTrustUrl(objectURL);
          });
        }
      },
        (err) => {
          this.snackbar.open('The training result does not exist', '', {
            duration: 3000
          });
        });
    }
  }

  ngOnInit(): void {
    this.refreshData();
  }

  onFormChange(): void {
    let selected_metrics = this.metricListControl.value;
    let res = []
    this.metrics_retrieved.forEach(function (value) {
      selected_metrics.forEach(function (metric) {
        if (value["name"].includes(metric)) {
          res.push(value)
        }
      })
    })
    this.data_shown = res;
  }

  exportJSON(data: any) {
    let csvContent = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data));
    let a = document.createElement('a');
    a.href = csvContent;
    if (data != this.conf_matrix_retrieved) {
      a.download = "metrics.json";
    } else {
      a.download = "conf_matrix.json";
    }
    a.click();
  }

}