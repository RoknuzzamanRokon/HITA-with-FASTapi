#!/usr/bin/env python3
"""
Performance test runner for user management system
Runs comprehensive performance tests and generates detailed reports
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from tests.performance_monitoring import (
    global_performance_collector, 
    global_concurrency_monitor,
    get_performance_report,
    reset_performance_monitoring
)
from tests.performance_report_generator import generate_performance_report
from tests.benchmark_config import BenchmarkConfig, PERFORMANCE_TEST_SCENARIOS


def run_performance_tests(
    test_file: str = "tests/test_performance.py",
    output_dir: str = "performance_reports",
    verbose: bool = True,
    generate_report: bool = True
) -> dict:
    """
    Run performance tests and generate reports
    
    Args:
        test_file: Path to performance test file
        output_dir: Directory to save reports
        verbose: Enable verbose output
        generate_report: Generate performance report after tests
    
    Returns:
        Dictionary with test results and performance metrics
    """
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Reset performance monitoring
    reset_performance_monitoring()
    
    print("=" * 80)
    print("USER MANAGEMENT SYSTEM - PERFORMANCE TESTS")
    print("=" * 80)
    print(f"Test file: {test_file}")
    print(f"Output directory: {output_dir}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Configure pytest arguments
    pytest_args = [
        test_file,
        "-v" if verbose else "-q",
        "--tb=short",
        "--disable-warnings",
        f"--junitxml={output_path}/performance_test_results.xml"
    ]
    
    # Add coverage if requested
    if os.getenv('COVERAGE', '').lower() == 'true':
        pytest_args.extend([
            "--cov=repositories",
            "--cov=services", 
            "--cov=cache_config",
            f"--cov-report=html:{output_path}/coverage_html",
            f"--cov-report=xml:{output_path}/coverage.xml"
        ])
    
    # Run tests
    start_time = time.time()
    exit_code = pytest.main(pytest_args)
    test_duration = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"Tests completed in {test_duration:.2f} seconds")
    print(f"Exit code: {exit_code}")
    
    # Generate performance report
    results = {
        'test_execution': {
            'exit_code': exit_code,
            'duration': test_duration,
            'timestamp': datetime.now().isoformat()
        }
    }
    
    if generate_report:
        print("Generating comprehensive performance report...")
        
        # Get comprehensive performance report
        performance_report = get_performance_report()
        results['performance_report'] = performance_report
        
        # Generate comprehensive report with visualizations
        try:
            report_files = generate_performance_report(results, str(output_path))
            
            print(f"JSON report saved to: {report_files['json_report']}")
            print(f"HTML report saved to: {report_files['html_report']}")
            
            # Also save the raw results
            raw_report_file = output_path / f"raw_performance_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(raw_report_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            print(f"Raw data saved to: {raw_report_file}")
            
            # Generate summary report
            generate_summary_report(results, output_path, report_files['report_data'])
            
        except Exception as e:
            print(f"Error generating comprehensive report: {e}")
            # Fallback to basic report
            report_file = output_path / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            print(f"Basic performance report saved to: {report_file}")
            generate_summary_report(results, output_path)
    
    print("=" * 80)
    
    return results


def generate_summary_report(results: dict, output_path: Path, comprehensive_report: dict = None):
    """Generate human-readable summary report"""
    
    summary_file = output_path / "performance_summary.txt"
    
    with open(summary_file, 'w') as f:
        f.write("USER MANAGEMENT SYSTEM - PERFORMANCE TEST SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        
        # Test execution summary
        test_info = results['test_execution']
        f.write(f"Test Execution:\n")
        f.write(f"  Duration: {test_info['duration']:.2f} seconds\n")
        f.write(f"  Exit Code: {test_info['exit_code']}\n")
        f.write(f"  Timestamp: {test_info['timestamp']}\n\n")
        
        # Performance metrics summary
        if 'performance_report' in results:
            perf_report = results['performance_report']
            
            if 'performance_metrics' in perf_report:
                metrics = perf_report['performance_metrics']
                overview = metrics.get('overview', {})
                
                f.write("Performance Overview:\n")
                f.write(f"  Total Queries: {overview.get('total_queries', 0)}\n")
                f.write(f"  Unique Queries: {overview.get('unique_queries', 0)}\n")
                f.write(f"  Cache Hit Rate: {overview.get('overall_cache_hit_rate', 0):.1%}\n")
                f.write(f"  Error Rate: {overview.get('overall_error_rate', 0):.1%}\n")
                f.write(f"  Recent Avg Time: {overview.get('recent_avg_time', 0):.3f}s\n")
                f.write(f"  Query Rate: {overview.get('recent_query_rate', 0):.1f} queries/min\n\n")
                
                # Top queries by frequency
                top_queries = metrics.get('top_queries', {})
                if 'by_frequency' in top_queries:
                    f.write("Top Queries by Frequency:\n")
                    for query_name, count in top_queries['by_frequency'][:5]:
                        f.write(f"  {query_name}: {count} executions\n")
                    f.write("\n")
                
                # Slowest queries
                if 'by_avg_time' in top_queries:
                    f.write("Slowest Queries:\n")
                    for query_name, avg_time in top_queries['by_avg_time'][:5]:
                        f.write(f"  {query_name}: {avg_time:.3f}s average\n")
                    f.write("\n")
                
                # Performance alerts
                alerts = metrics.get('alerts', [])
                if alerts:
                    f.write("Performance Alerts:\n")
                    for alert in alerts[:10]:  # Show top 10 alerts
                        f.write(f"  [{alert['severity'].upper()}] {alert['message']}\n")
                    f.write("\n")
                
                # Slow queries
                slow_queries = metrics.get('slow_queries', {})
                if slow_queries:
                    f.write("Slow Queries (above threshold):\n")
                    for query_name, stats in slow_queries.items():
                        f.write(f"  {query_name}: {stats['avg_time']:.3f}s average "
                               f"({stats['count']} executions)\n")
                    f.write("\n")
            
            # Concurrency statistics
            if 'concurrency_stats' in perf_report:
                concurrency = perf_report['concurrency_stats']
                f.write("Concurrency Statistics:\n")
                f.write(f"  Current Concurrent: {concurrency.get('current_concurrent', 0)}\n")
                f.write(f"  Max Concurrent (Ever): {concurrency.get('max_concurrent_ever', 0)}\n")
                f.write(f"  Max Concurrent (Recent): {concurrency.get('max_concurrent_recent', 0)}\n")
                f.write(f"  Avg Concurrent (Recent): {concurrency.get('avg_concurrent_recent', 0):.1f}\n")
                f.write(f"  Total Requests: {concurrency.get('total_requests', 0)}\n")
                f.write(f"  Avg Duration (Recent): {concurrency.get('avg_duration_recent', 0):.3f}s\n\n")
        
        # Recommendations
        f.write("Recommendations:\n")
        
        # Use comprehensive report recommendations if available
        if comprehensive_report and 'recommendations' in comprehensive_report:
            recommendations = comprehensive_report['recommendations']
            
            for category, recs in recommendations.items():
                if recs:
                    f.write(f"\n{category.upper()} RECOMMENDATIONS:\n")
                    for rec in recs:
                        f.write(f"  - {rec}\n")
        
        elif 'performance_report' in results:
            # Fallback to basic recommendations
            perf_report = results['performance_report']
            metrics = perf_report.get('performance_metrics', {})
            overview = metrics.get('overview', {})
            alerts = metrics.get('alerts', [])
            
            # Cache hit rate recommendations
            cache_hit_rate = overview.get('overall_cache_hit_rate', 0)
            if cache_hit_rate < 0.7:
                f.write(f"  - Improve cache hit rate (currently {cache_hit_rate:.1%})\n")
                f.write(f"    * Review cache TTL settings\n")
                f.write(f"    * Analyze cache key patterns\n")
                f.write(f"    * Consider cache warming strategies\n")
            
            # Slow query recommendations
            slow_queries = metrics.get('slow_queries', {})
            if slow_queries:
                f.write(f"  - Optimize {len(slow_queries)} slow queries:\n")
                for query_name in list(slow_queries.keys())[:3]:
                    f.write(f"    * {query_name}\n")
            
            # Error rate recommendations
            error_rate = overview.get('overall_error_rate', 0)
            if error_rate > 0.05:  # 5%
                f.write(f"  - Investigate high error rate ({error_rate:.1%})\n")
                f.write(f"    * Review error logs\n")
                f.write(f"    * Check database connectivity\n")
                f.write(f"    * Validate input parameters\n")
            
            # Performance alerts recommendations
            critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
            if critical_alerts:
                f.write(f"  - Address {len(critical_alerts)} critical performance issues\n")
            
            # General recommendations
            f.write(f"  - Monitor query performance regularly\n")
            f.write(f"  - Consider database indexing for frequently used queries\n")
            f.write(f"  - Implement query result pagination for large datasets\n")
            f.write(f"  - Use connection pooling for database connections\n")
        
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"Summary report saved to: {summary_file}")


def main():
    """Main entry point for performance test runner"""
    parser = argparse.ArgumentParser(description="Run user management performance tests")
    
    parser.add_argument(
        "--test-file", 
        default="tests/test_performance.py",
        help="Path to performance test file"
    )
    
    parser.add_argument(
        "--output-dir",
        default="performance_reports",
        help="Directory to save reports"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Run tests in quiet mode"
    )
    
    parser.add_argument(
        "--no-report",
        action="store_true", 
        help="Skip performance report generation"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate code coverage report"
    )
    
    parser.add_argument(
        "--scenario",
        choices=list(PERFORMANCE_TEST_SCENARIOS.keys()),
        help="Run specific performance test scenario"
    )
    
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run benchmark validation tests"
    )
    
    parser.add_argument(
        "--memory-profile",
        action="store_true",
        help="Include memory profiling tests"
    )
    
    parser.add_argument(
        "--cache-tests",
        action="store_true",
        help="Include cache monitoring tests"
    )
    
    args = parser.parse_args()
    
    # Set environment variables
    if args.coverage:
        os.environ['COVERAGE'] = 'true'
    
    if args.scenario:
        os.environ['PERFORMANCE_SCENARIO'] = args.scenario
    
    if args.benchmark:
        os.environ['RUN_BENCHMARKS'] = 'true'
    
    if args.memory_profile:
        os.environ['MEMORY_PROFILE'] = 'true'
    
    if args.cache_tests:
        os.environ['CACHE_TESTS'] = 'true'
    
    # Run performance tests
    try:
        results = run_performance_tests(
            test_file=args.test_file,
            output_dir=args.output_dir,
            verbose=not args.quiet,
            generate_report=not args.no_report
        )
        
        # Exit with test exit code
        sys.exit(results['test_execution']['exit_code'])
        
    except KeyboardInterrupt:
        print("\nPerformance tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error running performance tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()