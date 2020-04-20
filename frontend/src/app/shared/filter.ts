import {Pipe, PipeTransform} from '@angular/core'; 

@Pipe({
    name: 'datafilter'
  })
  export class DataFilterPipe implements PipeTransform {
    transform(items: any[], searchText: string): any[] {
    if(!items) return [];
    if(!searchText) return items;
    searchText = searchText.toLowerCase();

    return items.filter(item => {
        return Object.keys(item).find(key => String(item[key]).toLowerCase().includes(searchText));
    });
    }
  }