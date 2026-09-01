import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App, HttpClientTestingModule],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should show the role selector in register mode', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;

    app.mode = 'register';
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const select = compiled.querySelector('select[name="role"]');

    expect(app.roleOptions.length).toBe(3);
    expect(select).not.toBeNull();
    expect(select?.textContent).toContain('Simple utilisateur');
    expect(select?.textContent).toContain('Responsable de secteur');
  });
});
