import { TestBed } from '@angular/core/testing';

import { VisualizationWsService } from './visualization-ws.service';

describe('VisualizationWsService', () => {
  let service: VisualizationWsService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(VisualizationWsService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
