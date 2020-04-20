import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'maxChar'
})
export class MaxCharPipe implements PipeTransform {

  transform(value: string, limit: number): string {
    return value.substr(0, limit).trim() + '...';
  }

}
